"""SAML 2.0 SP for Okta (or any SAML IdP).

Uses ``python3-saml``. We stay SP-initiated for simplicity; IdP-initiated flows can be
enabled by exposing an unsolicited response path. SAML Responses are signed, and we
verify signature + conditions + audience + notBefore/notOnOrAfter.

Cert/key pair sits in ``settings.saml_cert_dir``:
  - sp.crt / sp.key : Kynara SP cert + private key
  - <org>.idp.crt   : IdP signing cert per org (populated when admin pastes it in UI)
"""
from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.models import SsoConnection


def _settings_dict(conn: SsoConnection) -> dict[str, Any]:
    s = get_settings()
    return {
        "strict": True,
        "debug": not s.is_prod,
        "sp": {
            "entityId": s.saml_sp_entity_id,
            "assertionConsumerService": {
                "url": s.saml_sp_acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        },
        "idp": {
            "entityId": conn.idp_entity_id,
            "singleSignOnService": {
                "url": conn.idp_sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": conn.idp_x509_cert,
        },
        "security": {
            "authnRequestsSigned": True,
            "wantAssertionsSigned": True,
            "wantMessagesSigned": False,
            "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
            "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
        },
    }


def build_login_redirect(conn: SsoConnection, return_to: str | None = None) -> str:
    """Return the Okta SSO URL the browser should be redirected to (SP-initiated)."""
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

    req = {"https": "on", "http_host": "kynara.dev", "script_name": "/", "get_data": {}, "post_data": {}}
    auth = OneLogin_Saml2_Auth(req, old_settings=_settings_dict(conn))
    return auth.login(return_to or "/")


def parse_acs(
    conn: SsoConnection,
    post_data: dict[str, Any],
    host: str,
) -> dict[str, Any]:
    """Verify the SAML Response and return a dict of attributes (email, nameID, ...)."""
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

    req = {
        "https": "on",
        "http_host": host,
        "script_name": "/api/v1/auth/sso/saml/acs",
        "get_data": {},
        "post_data": post_data,
    }
    auth = OneLogin_Saml2_Auth(req, old_settings=_settings_dict(conn))
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        raise PermissionError("SAML response invalid: " + ", ".join(errors))
    if not auth.is_authenticated():
        raise PermissionError("SAML response not authenticated")

    attrs = auth.get_attributes() or {}
    return {
        "name_id": auth.get_nameid(),
        "session_index": auth.get_session_index(),
        "attributes": {k: (v[0] if v else None) for k, v in attrs.items()},
    }
