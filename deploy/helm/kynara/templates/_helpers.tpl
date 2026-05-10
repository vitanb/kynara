{{- define "kynara.name" -}}{{- .Chart.Name -}}{{- end -}}
{{- define "kynara.fullname" -}}{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}{{- end -}}
{{- define "kynara.labels" -}}
app.kubernetes.io/name: {{ include "kynara.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "kynara.backend.image" -}}
{{ .Values.backend.image.repository }}:{{ default .Chart.AppVersion .Values.backend.image.tag }}
{{- end -}}

{{- define "kynara.sidecar.image" -}}
{{ .Values.sidecar.image.repository }}:{{ default .Chart.AppVersion .Values.sidecar.image.tag }}
{{- end -}}
