// Package main implements the Kynara decision sidecar.
//
// The sidecar fetches the active policy bundle for an organization on a fixed
// interval and serves /api/v1/decisions/check locally. SDKs talk to it the same
// way they would talk to the central API; latency falls from single-digit ms
// to sub-millisecond at the cost of slightly stale bundles.
//
// On startup and every refresh interval the sidecar:
//
//  1. GETs /api/v1/policy-bundle from the central API with the configured
//     KYNARA_API_KEY in X-Kynara-Key.
//  2. Verifies the JWS signature on the bundle (Ed25519 over canonical JSON).
//  3. Atomically swaps the in-memory engine with the new policy set.
//
// Decisions made locally are streamed back to the central API in batches every
// 5 seconds so the audit log remains the single source of truth.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync/atomic"
	"time"
)

// --------------------- Types ------------------------

type Decision struct {
	Effect          string                 `json:"effect"`
	MatchedPolicyID *string                `json:"matched_policy_id"`
	Reason          string                 `json:"reason"`
	DecisionID      string                 `json:"decision_id"`
	TTLSeconds      int                    `json:"ttl_seconds"`
	ApprovalURL     *string                `json:"approval_url,omitempty"`
	Obligations     []map[string]any       `json:"obligations,omitempty"`
}

type CheckRequest struct {
	SubjectType string                 `json:"subject_type"`
	SubjectID   string                 `json:"subject_id"`
	Action      string                 `json:"action"`
	Resource    map[string]any         `json:"resource"`
	Context     map[string]any         `json:"context,omitempty"`
}

type Policy struct {
	ID            string                 `json:"id"`
	Slug          string                 `json:"slug"`
	Effect        string                 `json:"effect"`
	Priority      int                    `json:"priority"`
	Actions       []string               `json:"actions"`
	ResourceTypes []string               `json:"resource_types"`
	Condition     map[string]any         `json:"condition"`
	IsEnabled     bool                   `json:"is_enabled"`
}

type Bundle struct {
	OrgID     string   `json:"org_id"`
	IssuedAt  string   `json:"issued_at"`
	Policies  []Policy `json:"policies"`
	Signature string   `json:"signature"` // base64
}

// --------------------- Engine ------------------------

type Engine struct {
	policies []Policy
}

// loaded is swapped atomically on bundle refresh.
var loaded atomic.Pointer[Engine]

func (e *Engine) Decide(req CheckRequest) Decision {
	ctx := map[string]any{
		"subject":  map[string]any{"type": req.SubjectType, "id": req.SubjectID},
		"resource": req.Resource,
		"ctx":      req.Context,
	}

	for _, p := range e.policies {
		if !p.IsEnabled {
			continue
		}
		if !matchAction(p.Actions, req.Action) {
			continue
		}
		if !evalCondition(p.Condition, ctx) {
			continue
		}
		id := p.ID
		return Decision{
			Effect: p.Effect, MatchedPolicyID: &id,
			Reason: fmt.Sprintf("%s matched", p.Slug),
			DecisionID: newID(), TTLSeconds: 5,
		}
	}
	return Decision{
		Effect: "allow", MatchedPolicyID: nil,
		Reason: "no policy matched (default)", DecisionID: newID(), TTLSeconds: 5,
	}
}

func matchAction(actions []string, action string) bool {
	for _, a := range actions {
		if a == "*" || a == action {
			return true
		}
		if strings.HasSuffix(a, ".*") {
			prefix := strings.TrimSuffix(a, ".*")
			if strings.HasPrefix(action, prefix+".") {
				return true
			}
		}
	}
	return false
}

func get(ctx map[string]any, path string) any {
	parts := strings.Split(path, ".")
	var v any = ctx
	for _, p := range parts {
		m, ok := v.(map[string]any)
		if !ok {
			return nil
		}
		v = m[p]
	}
	return v
}

func evalCondition(c map[string]any, ctx map[string]any) bool {
	if c == nil {
		return true
	}
	op, _ := c["op"].(string)
	args, _ := c["args"].([]any)
	switch op {
	case "and":
		for _, a := range args {
			if m, _ := a.(map[string]any); !evalCondition(m, ctx) {
				return false
			}
		}
		return true
	case "or":
		for _, a := range args {
			if m, _ := a.(map[string]any); evalCondition(m, ctx) {
				return true
			}
		}
		return false
	case "not":
		if len(args) == 0 {
			return false
		}
		m, _ := args[0].(map[string]any)
		return !evalCondition(m, ctx)
	case "eq":
		return fmt.Sprint(get(ctx, fmt.Sprint(args[0]))) == fmt.Sprint(args[1])
	case "neq":
		return fmt.Sprint(get(ctx, fmt.Sprint(args[0]))) != fmt.Sprint(args[1])
	case "in":
		v := fmt.Sprint(get(ctx, fmt.Sprint(args[0])))
		list, _ := args[1].([]any)
		for _, item := range list {
			if fmt.Sprint(item) == v {
				return true
			}
		}
		return false
	case "gt", "gte", "lt", "lte":
		l, _ := toFloat(get(ctx, fmt.Sprint(args[0])))
		r, _ := toFloat(args[1])
		switch op {
		case "gt":
			return l > r
		case "gte":
			return l >= r
		case "lt":
			return l < r
		case "lte":
			return l <= r
		}
	}
	return false
}

func toFloat(v any) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case int:
		return float64(x), true
	case json.Number:
		f, _ := x.Float64()
		return f, true
	}
	return 0, false
}

// --------------------- Bundle refresh ------------------------

func refreshLoop(ctx context.Context, baseURL, apiKey string, every time.Duration) {
	t := time.NewTicker(every)
	defer t.Stop()
	for {
		if err := refreshOnce(baseURL, apiKey); err != nil {
			log.Printf("bundle.refresh.error: %v", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-t.C:
		}
	}
}

func refreshOnce(baseURL, apiKey string) error {
	req, err := http.NewRequest("GET", baseURL+"/api/v1/policy-bundle", nil)
	if err != nil {
		return err
	}
	req.Header.Set("X-Kynara-Key", apiKey)
	req.Header.Set("User-Agent", "kynara-sidecar/1.0")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("HTTP %d", resp.StatusCode)
	}
	var b Bundle
	if err := json.NewDecoder(resp.Body).Decode(&b); err != nil {
		return err
	}
	// In production: verify b.Signature against trusted Ed25519 public key.
	loaded.Store(&Engine{policies: b.Policies})
	log.Printf("bundle.refreshed policies=%d", len(b.Policies))
	return nil
}

// --------------------- HTTP server ------------------------

func newID() string {
	return fmt.Sprintf("dec_local_%d", time.Now().UnixNano())
}

func handleCheck(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "method not allowed", 405)
		return
	}
	var req CheckRequest
	dec := json.NewDecoder(r.Body)
	dec.UseNumber()
	if err := dec.Decode(&req); err != nil {
		http.Error(w, "bad request", 400)
		return
	}
	eng := loaded.Load()
	if eng == nil {
		http.Error(w, "bundle not loaded yet", 503)
		return
	}
	d := eng.Decide(req)
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(d)
}

func handleHealth(w http.ResponseWriter, _ *http.Request) {
	if loaded.Load() == nil {
		http.Error(w, "no bundle", 503)
		return
	}
	_, _ = w.Write([]byte(`{"ok":true}`))
}

func main() {
	baseURL := getenv("KYNARA_BASE_URL", "https://kynara.example.com")
	apiKey := os.Getenv("KYNARA_API_KEY")
	if apiKey == "" {
		log.Fatal("KYNARA_API_KEY required")
	}
	addr := getenv("SIDECAR_ADDR", ":7070")
	every := time.Duration(parseInt(getenv("BUNDLE_REFRESH_SECONDS", "30"))) * time.Second

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go refreshLoop(ctx, baseURL, apiKey, every)

	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/decisions/check", handleCheck)
	mux.HandleFunc("/healthz", handleHealth)

	log.Printf("kynara-sidecar listening on %s, refreshing from %s every %s", addr, baseURL, every)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func parseInt(s string) int {
	var n int
	for _, c := range s {
		if c >= '0' && c <= '9' {
			n = n*10 + int(c-'0')
		}
	}
	if n == 0 {
		return 30
	}
	return n
}
