"""Radar de suscripciones: detecta alertas de caída/pago en correos de streaming.

Regla de exclusión estricta: NO extraemos códigos OTP ni PINs. Solo
clasificamos el correo como alerta crítica si viene de un dominio de streaming
y contiene una palabra clave de problema de suscripción.
"""

from __future__ import annotations

# Dominios de servicios de streaming (se hace match por "contiene").
STREAMING_DOMAINS: dict[str, str] = {
    "netflix": "Netflix",
    "hbomax": "HBO Max",
    "max.com": "Max",
    "primevideo": "Prime Video",
    "amazon": "Prime Video",
    "disney": "Disney+",
    "disneyplus": "Disney+",
    "spotify": "Spotify",
    "hulu": "Hulu",
    "paramount": "Paramount+",
    "crunchyroll": "Crunchyroll",
    "youtube": "YouTube Premium",
    "star": "Star+",
    "vix": "ViX",
    "appletv": "Apple TV+",
    "apple.com": "Apple TV+",
}

# Palabras clave de problema (multi-idioma). NO incluye códigos/OTP.
ALERT_KEYWORDS: list[str] = [
    # español
    "pago", "actualizar", "actualiza", "rechazado", "rechazada",
    "caducada", "caducado", "cancelada", "cancelado", "vencida", "vencido",
    "suspendida", "suspendido", "problema con el pago", "método de pago",
    "no pudimos", "fallo", "falló", "renovar", "renovación",
    # inglés
    "payment", "update", "declined", "expired", "cancelled", "canceled",
    "suspended", "hold", "failed", "renew", "billing",
    # portugués
    "pagamento", "atualizar", "recusado", "expirada", "cancelada",
    # italiano
    "pagamento", "aggiornare", "rifiutato", "scaduta",
]


def detect(from_addr: str, subject: str, body_text: str) -> tuple[bool, str, str]:
    """Devuelve (es_alerta, servicio, keyword).

    Es alerta solo si el remitente es de un dominio de streaming Y aparece
    alguna keyword de problema en asunto o cuerpo.
    """
    sender = (from_addr or "").lower()
    service = ""
    for domain, name in STREAMING_DOMAINS.items():
        if domain in sender:
            service = name
            break
    if not service:
        return False, "", ""

    haystack = f"{subject or ''} {body_text or ''}".lower()
    for kw in ALERT_KEYWORDS:
        if kw in haystack:
            return True, service, kw

    return False, "", ""
