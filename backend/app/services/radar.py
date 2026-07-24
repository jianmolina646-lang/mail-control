"""Clasificador determinista de estados de suscripciones.

No extrae OTP, PIN, enlaces ni credenciales. Solo clasifica mensajes enviados
desde dominios conocidos y utiliza frases contextualizadas para evitar que una
palabra genérica como ``payment`` produzca una alerta falsa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parseaddr


@dataclass(frozen=True)
class Classification:
    service: str = ""
    status: str = "unknown"
    severity: str = "info"
    reason: str = ""
    score: int = 0

    @property
    def is_alert(self) -> bool:
        return self.status in {"warning", "payment_failed", "suspended", "cancelled"}


# Un dominio coincide solo si es exacto o un subdominio. Nunca por texto libre.
SERVICE_DOMAINS: dict[str, tuple[str, ...]] = {
    "Netflix": ("netflix.com",),
    "Prime Video": ("amazon.com", "amazon.es", "amazon.com.mx", "primevideo.com"),
    "Disney+": ("disneyplus.com", "disney.com"),
    "Max": ("max.com", "hbomax.com"),
    "Spotify": ("spotify.com",),
    "Paramount+": ("paramountplus.com", "paramount.com"),
    "YouTube Premium": ("youtube.com", "google.com"),
    "Apple TV+": ("apple.com",),
    "Crunchyroll": ("crunchyroll.com",),
    "Hulu": ("hulu.com",),
    "ViX": ("vix.com",),
}

# Se evalúan primero los estados más graves. Una coincidencia en el asunto pesa
# más que una en el cuerpo.
STATUS_RULES: dict[str, tuple[int, str, tuple[str, ...]]] = {
    "suspended": (
        5, "Cuenta suspendida",
        (
            "account suspended", "membership suspended", "cuenta suspendida",
            "suscripción suspendida", "suscripcion suspendida", "acceso suspendido",
            "account locked due to billing", "conta suspensa",
        ),
    ),
    "payment_failed": (
        5, "Pago rechazado",
        (
            "payment failed", "payment was declined", "card declined",
            "unable to process your payment", "couldn't process your payment",
            "could not process your payment", "pago rechazado", "pago fallido",
            "no pudimos procesar tu pago", "no se pudo procesar el pago",
            "tarjeta rechazada", "pagamento recusado", "pagamento falhou",
        ),
    ),
    "cancelled": (
        5, "Suscripción cancelada",
        (
            "subscription cancelled", "subscription canceled", "membership cancelled",
            "membership canceled", "suscripción cancelada", "suscripcion cancelada",
            "membresía cancelada", "membresia cancelada",
        ),
    ),
    "warning": (
        3, "Requiere actualización",
        (
            "update payment method", "update your payment", "payment method expires",
            "card is expiring", "action required: payment", "billing information",
            "actualiza tu método de pago", "actualizar método de pago",
            "actualiza tu metodo de pago", "tarjeta está por vencer",
            "tarjeta esta por vencer", "atualize sua forma de pagamento",
        ),
    ),
    "active": (
        3, "Suscripción activa",
        (
            "payment successful", "payment received", "membership reactivated",
            "subscription renewed", "renewal confirmed", "membership is active",
            "pago realizado", "pago aprobado", "pago recibido",
            "suscripción renovada", "suscripcion renovada", "membresía reactivada",
            "membresia reactivada", "renovación confirmada", "renovacion confirmada",
        ),
    ),
}

NEGATIVE_CONTEXT = (
    "welcome", "bienvenido", "verify your email", "verifica tu correo",
    "new sign-in", "nuevo inicio de sesión", "nuevo inicio de sesion",
)

SERVICE_CONTEXT: dict[str, tuple[str, ...]] = {
    "Prime Video": ("prime", "prime video", "membership", "membresía", "membresia"),
    "YouTube Premium": ("youtube premium", "youtube music"),
    "Apple TV+": ("apple tv", "apple one"),
}


def _sender_domain(from_addr: str) -> str:
    address = parseaddr(from_addr or "")[1].lower().strip()
    if "@" not in address:
        return ""
    domain = address.rsplit("@", 1)[1].rstrip(".")
    return domain if re.fullmatch(r"[a-z0-9.-]+", domain) else ""


def _service_for_domain(domain: str) -> str:
    for service, trusted_domains in SERVICE_DOMAINS.items():
        if any(domain == trusted or domain.endswith(f".{trusted}") for trusted in trusted_domains):
            return service
    return ""


def classify(from_addr: str, subject: str, body_text: str) -> Classification:
    service = _service_for_domain(_sender_domain(from_addr))
    if not service:
        return Classification()

    subject_text = (subject or "").casefold()
    body = (body_text or "").casefold()[:50_000]
    context = f"{subject_text} {body}"
    required_context = SERVICE_CONTEXT.get(service)
    if required_context and not any(term.casefold() in context for term in required_context):
        return Classification()
    best = Classification(service=service)

    for status, (base_score, reason, phrases) in STATUS_RULES.items():
        for phrase in phrases:
            normalized = phrase.casefold()
            score = 0
            if normalized in subject_text:
                score = base_score + 3
            elif normalized in body:
                score = base_score
            if score and status != "active" and any(term in subject_text for term in NEGATIVE_CONTEXT):
                score -= 2
            if score > best.score:
                severity = (
                    "critical" if status in {"payment_failed", "suspended", "cancelled"}
                    else "warning" if status == "warning"
                    else "info"
                )
                best = Classification(service, status, severity, reason, score)

    return best if best.score >= 3 else Classification(service=service)


def detect(from_addr: str, subject: str, body_text: str) -> tuple[bool, str, str]:
    """Compatibilidad con llamadas antiguas."""
    result = classify(from_addr, subject, body_text)
    return result.is_alert, result.service, result.reason
