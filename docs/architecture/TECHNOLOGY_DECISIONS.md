# Technology Decisions

These are candidate implementation choices for the Kenvue landscape. The logical architecture remains platform-independent and all placements are subject to approved enterprise standards.

| Capability | Why required | Recommended candidate | Alternatives | Boundary |
|---|---|---|---|---|
| Databricks | Scalable engineering, governed data products, analytics and AI/ML | Databricks + Delta Lake | Approved lakehouse equivalent | Do not turn every application transaction into a lakehouse operation |
| dbt | Transparent, versioned analytical transformations and tests | dbt on Databricks | Native SQL/jobs | Not an operational workflow engine |
| Unity Catalog | Catalog, permissions, lineage and data governance | Unity Catalog | Enterprise catalog equivalent | Not a substitute for metric semantics or approval workflow |
| Lakeflow / Jobs | Scheduled and incremental data processing | Lakeflow / Databricks Jobs | Enterprise scheduler | Not durable human workflow state |
| Genie | Governed natural-language analysis of structured curated data | Databricks Genie | Semantic BI assistant | Do not use as signal engine, contract manager, truth store, approval engine or transaction coordinator |
| MLflow 3 | Model/agent evaluation, quality, cost and traceability | MLflow 3 | Enterprise AI evaluation stack | Not the business decision system |
| AKS | Horizontally scalable application and agent runtime | Kubernetes / AKS | Approved container runtime | Not the analytical storage plane |
| Kong | API gateway, routing, policy and edge controls | Kong | Enterprise API gateway | Not workflow persistence |
| Nexus | Container and artifact supply chain | Nexus | Approved artifact registry | Not source data landing |
| PostgreSQL | Operational metadata, API state and transactional records | PostgreSQL | Approved relational OLTP | Not the multi-year analytical lakehouse |
| Redis | Cache and short-lived coordination | Redis | Approved cache | Not system-of-record state |
| Temporal | Durable long-running process orchestration and retries | Temporal | Approved workflow engine | Not an analytical transformation engine |
| Service Bus / Event Hub | Event transport and decoupled acquisition | Azure Service Bus / Event Hub | Approved messaging | Not a substitute for immutable raw storage |
| Azure AI Search / Vector Search | Governed retrieval over evidence and approved content | Azure AI Search / Databricks Vector Search | Approved search/vector layer | Retrieval must preserve source lineage and access policy |
| Key Vault | Secret storage and rotation | Azure Key Vault | Approved secrets manager | Never place secrets in prompts, logs or source files |
| OpenTelemetry | Consistent traces, metrics and logs across services | OpenTelemetry + enterprise monitoring | Equivalent telemetry standard | Must exclude secrets and sensitive payloads |
| Agent framework | Pluggable orchestration of typed tools and bounded context | LangGraph / Semantic Kernel / Databricks agent capability | Other approved framework | Agents assist decisions; they do not become the platform brain |
| App / consumption | Business experience and enterprise intelligence | Web app, APIs, Command Centre / KIIP where appropriate | BI or portal equivalent | KIIP is a candidate channel, not a logical dependency |

## Deliberate boundaries

- **Genie:** use for governed natural-language structured-data analysis. Do not use as the signal engine, schema/metric contract manager, enterprise truth store, business approval engine or general multi-system transaction coordinator.
- **Temporal:** use for durable long-running process orchestration. Do not use as the analytical transformation engine.
- **dbt:** use for transparent/versioned analytical transformation. Do not use as operational workflow storage.
- **Databricks:** use for data engineering, governance, data products, analytics and AI/ML capabilities. Keep application transactions in the operational boundary.
