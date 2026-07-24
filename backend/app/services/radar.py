"""Radar de suscripciones: detecta alertas de caída/pago en correos de streaming.

Regla de exclusión estricta: NO extraemos códigos OTP ni PINs. Solo
clasificamos el correo como alerta crítica si viene de un dominio de streaming
y contiene una palabra clave de problema de suscripción.
"""

from __future__ import annotations

# Dominios de servicios de streaming (se hace match por "contiene").
STREAMING_DOMAINS: dict[str, str] = {
    # Plataformas principales
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
    "youtubemusic": "YouTube Music",
    "star": "Star+",
    "vix": "ViX",
    "appletv": "Apple TV+",
    "apple.com": "Apple TV+",
    # Regionales y adicionales
    "disneystars": "Disney Star",
    "peacock": "Peacock",
    "mubi": "MUBI",
    "criterion": "Criterion",
    "showtime": "Showtime",
    "acorntvplus": "Acorn TV",
    "britbox": "BritBox",
    "kanopy": "Kanopy",
    "hooplala": "Hoopla",
    "pluto": "Pluto TV",
    "tubi": "Tubi",
    "freevee": "FreeVee",
    "cinemax": "Cinemax",
    "starz": "Starz",
    "sundancenow": "Sundance Now",
    "tcm": "TCM",
    "turner": "Turner",
    "twitch": "Twitch",
    "kick": "Kick",
    "bilibili": "BiliBili",
    "iqiyi": "iQIYI",
    "mydramalist": "MyDramaList",
    "wetv": "WeTV",
    "aha": "Aha",
    "hotstar": "Disney Hotstar",
    "zee5": "ZEE5",
    "sonyliv": "SonyLIV",
    "voot": "Voot",
    "alibaba": "Alibaba",
    "vudu": "Vudu",
    "redbox": "Redbox",
    "fubo": "Fubo",
    "sling": "Sling",
    "philo": "Philo",
    # Música y podcasts
    "applemusic": "Apple Music",
    "musicapple": "Apple Music",
    "tidal": "TIDAL",
    "soundcloud": "SoundCloud",
    "deezer": "Deezer",
    # Otros servicios
    "audible": "Audible",
    "skillshare": "Skillshare",
    "masterclass": "MasterClass",
    "udemy": "Udemy",
    "coursera": "Coursera",
}

# Palabras clave de problema (multi-idioma). NO incluye códigos/OTP.
ALERT_KEYWORDS: list[str] = [
    # ESPAÑOL - Pagos/Problemas
    "pago", "actualizar", "actualiza", "rechazado", "rechazada",
    "caducada", "caducado", "cancelada", "cancelado", "vencida", "vencido",
    "suspendida", "suspendido", "problema con el pago", "método de pago",
    "no pudimos", "fallo", "falló", "renovar", "renovación",
    "tarjeta rechazada", "pago no completado", "cuenta suspendida",
    "acceso denegado", "no autorizado", "verificación fallida",
    "límite de intentos", "cuenta bloqueada", "inactiva",
    
    # ESPAÑOL - Estado/Cambios
    "activo", "activada", "activación", "confirmado", "confirmada",
    "renovada", "renovado", "vigente", "suscrito", "suscrita",
    "confirmación", "verificado", "validado", "habilitado",
    
    # INGLÉS - Pagos/Problemas
    "payment", "update", "declined", "expired", "cancelled", "canceled",
    "suspended", "hold", "failed", "renew", "billing",
    "card declined", "payment failed", "account suspended",
    "access denied", "unauthorized", "verification failed",
    "attempt limit", "account locked", "inactive",
    
    # INGLÉS - Estado/Cambios
    "active", "activated", "activation", "confirmed", "confirmation",
    "renewed", "valid", "subscribed", "verified", "enabled",
    
    # PORTUGUÉS - Pagos/Problemas
    "pagamento", "atualizar", "recusado", "expirada", "cancelada",
    "suspensa", "falha", "falhou", "renovar", "renovação",
    "cartão recusado", "pagamento não efetuado", "conta suspensa",
    "acesso negado", "não autorizado", "verificação falhou",
    
    # PORTUGUÉS - Estado/Cambios
    "ativo", "ativada", "ativação", "confirmado", "confirmada",
    "renovada", "renovado", "vigente", "inscrito", "inscrita",
    
    # ITALIANO - Pagos/Problemas
    "pagamento", "aggiornare", "rifiutato", "scaduta", "cancellata",
    "sospesa", "errore", "fallito", "rinnovare", "rinnovo",
    "carta rifiutata", "pagamento non riuscito", "account sospeso",
    
    # ITALIANO - Estado/Cambios
    "attivo", "attivata", "attivazione", "confermato", "confermata",
    "rinnovata", "rinnovato", "valido", "iscritto", "iscritta",
    
    # PALABRAS CLAVE DE URGENCIA (Cualquier idioma)
    "urgente", "urgent", "importante", "important", "aviso", "notice",
    "alert", "alerta", "crítico", "critical", "critical",
    "atención", "attention", "requiere", "requires", "acción",
    "action", "inmediato", "immediate", "pronto", "soon",
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
