# ADR-0001: monolito modular con procesos especializados

## Estado

Aceptado.

## Decisión

El dominio vivirá inicialmente en un único repositorio y paquete, dividido en
módulos con límites explícitos. API, workers, scheduler y receptor de webhooks
serán procesos desplegables independientes que reutilizan los mismos casos de
uso.

PostgreSQL es la fuente de verdad, RabbitMQ transporta trabajos duraderos y
Redis almacena únicamente estado efímero.

## Motivo

El producto necesita crecer desde decenas hasta miles de cuentas sin pagar,
desde el primer día, el costo operativo y transaccional de microservicios. Los
puertos y adaptadores permiten extraer un módulo cuando las métricas demuestren
que necesita escalado o despliegue independiente.

## Consecuencias

- Ningún módulo consulta directamente tablas ajenas.
- Los eventos que salen de una transacción usarán un transactional outbox.
- No se crearán migraciones en tiempo de arranque.
- Toda entidad comercial incorporará tenant y auditoría desde la Fase 1.
