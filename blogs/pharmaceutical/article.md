# What Would It Take for a Pharma Company to Run AI On Its Own Infrastructure?

*For R&D leaders, CIOs, and digital transformation executives evaluating AI solutions for their organization.*

*This article is for informational purposes only and does not constitute regulatory, legal, or compliance advice. Organizations should evaluate AI deployments with qualified professionals based on their specific regulatory obligations and risk profile.*

<!-- TODO: Replace with hero image for social sharing previews -->
![Private AI for Pharma](images/hero.png)

---

## The Problem With Third-Party AI in Pharma

In 2023, Samsung [banned employees from using ChatGPT](https://mashable.com/article/samsung-chatgpt-leak-leads-to-employee-ban) after engineers inadvertently uploaded proprietary source code and internal meeting notes to the service - data that could be stored on external servers and potentially used for model training. Samsung wasn't a pharma company, but the lesson landed hard across the industry: if it can happen with source code, it can happen with compound structures, clinical trial data, and manufacturing processes.

The pharma industry's exposure is particularly acute. A 2024 Kiteworks study found that [**83% of pharmaceutical companies operate without automated safeguards**](https://www.contractpharma.com/exclusives/ai-data-security-the-83-compliance-gap-facing-pharmaceutical-companies/) to prevent sensitive data from leaking through AI tools. Only 17% have implemented technical controls like DLP scanning. The rest rely on training emails (40%), warnings without follow-up (20%), or have no AI usage policy at all (13%). Meanwhile, 27% of life sciences organizations report that over 30% of their AI-handled data contains sensitive or proprietary content.

This creates a paradox: the data that would benefit most from AI analysis - pre-IND compound structures, clinical endpoint designs, manufacturing process parameters - is the data organizations can least afford to send to a third-party API. And the regulatory environment makes the problem harder, not easier, to solve.

---

## Three Risks That Keep R&D Leaders Up at Night

### 1. Intellectual Property Leaves the Building

Your pipeline is your competitive advantage. Pre-IND compound structures, unpublished mechanism-of-action data, manufacturing process parameters - this is the intellectual property that underpins billions in R&D investment. Sending it to a cloud LLM means relinquishing physical control. Even with contractual protections, once data hits a third-party API, you cannot verify how it's stored, cached, or used downstream. For organizations where a single patent filing depends on maintaining trade secret protection, that risk may be difficult to accept.

### 2. The Regulatory Traceability Gap

AI isn't exempt from GxP. If a scientist uses an LLM to draft a clinical study report section, summarize adverse events, or review CMC documentation, the tool that produced that output falls under the same scrutiny as any computerized system in a regulated environment. [FDA 21 CFR Part 11](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11) requires electronic records with audit trails, access controls, and attributable authorship. [EMA Annex 11](https://health.ec.europa.eu/system/files/2016-11/annex11_01-2011_en_0.pdf) imposes equivalent requirements. A SaaS tool that cannot provide attributable, auditable records of who asked what, when, and what sources informed the answer may not satisfy these requirements.

### 3. Hallucinations Compound Through the Pipeline

When an AI fabricates a drug-drug interaction, misattributes a clinical outcome to the wrong study arm, or cites a retracted paper, the consequences aren't just embarrassing - they can contaminate safety assessments, mislead regulatory reviewers, and delay or derail programs worth hundreds of millions. Scientists need AI-generated claims traceable to a source document they can verify themselves. **All AI-generated content must be reviewed by qualified personnel before use in any decision-making, clinical, or regulatory context.**

The common thread: some organizations are asking whether AI infrastructure they can *deploy inside their own walls*, *validate against their own standards*, and *audit with their own tools* might be worth exploring.

---

## What "AI You Control" Looks Like in Practice

Self-hosting changes the equation. Instead of trusting vendor claims about data handling, you inspect the infrastructure yourself. But what does that actually look like inside a pharma organization?

[Open WebUI](https://docs.openwebui.com/) is a general-purpose, open-source AI platform that can be self-hosted. It's one example of a platform that can be configured to address these concerns - organizations should evaluate whether and how its capabilities fit their own regulatory, quality, and governance requirements.

Here's how different teams across a pharma organization might interact with a self-hosted AI platform, depending on how it's configured:

> **Note:** The following scenarios are illustrative and do not represent validated or endorsed workflows. Any use of AI-generated content in regulatory submissions requires your organization's own validation, human expert review, and quality sign-off processes. Open WebUI is a general-purpose tool - it does not replace these processes.

**A scientist in R&D** queries the company's internal compound library: *"Summarize the primary efficacy endpoints from our internal studies for compound X, including the statistical methods used."* The response pulls from internal study reports and cites each by document name with relevance scores. She clicks each citation to verify it against the source PDF. The scientist has access to compound libraries and assay protocols; she cannot see manufacturing SOPs or pharmacovigilance data. The entire exchange is logged under her SSO identity.

**A regulatory affairs specialist** is drafting a response to an FDA deficiency letter. She queries the precedent correspondence knowledge base: *"Find examples of how we've previously addressed CMC deficiency observations related to dissolution testing."* The platform retrieves relevant passages from prior FDA interactions and cites the specific documents. She reviews, edits, and routes the content through her organization's quality procedures before it goes anywhere near a submission.

**A pharmacovigilance officer** reviews a safety signal. His group has been configured with RAG-only access to curated safety databases - no web search, no file upload, no general-purpose chat. The platform prioritizes retrieval from MedDRA dictionaries and signal detection SOPs. He knows the underlying model may still draw on its training data, so he verifies every claim against the source documents before including anything in a safety assessment.

Later, when a question arises about how a specific claim was drafted, the team can review the conversation log: the query, the AI response, the source documents cited, and the timestamp - attributable to a named user and retained on company-controlled infrastructure when configured for local-only operation.

<!-- TODO: Replace with real screenshot of chat UI showing inline citations and source panel -->
![Open WebUI chat interface with document citations and relevance scores](images/chat_citations.png)

---

## Mapping AI to Your Organizational Structure

The scenarios above depend on one thing: each functional group seeing only the models, documents, and capabilities assigned to it. Open WebUI includes a group-based access control system that can map to your organizational structure. **The table below is an illustrative configuration - organizations should design their own group structure based on their specific functional areas, risk profile, and governance requirements.**

<!-- TODO: Replace with screenshot of Admin Panel → Groups showing functional groups -->
![Admin panel showing functional group configuration](images/admin_groups.png)

| Functional Group | AI Capabilities | Knowledge Bases | Special Permissions |
|---|---|---|---|
| **R&D / Discovery** | Full | Compound libraries, assay protocols, literature databases | Code interpreter *(run analysis scripts on screening data)* |
| **Clinical Operations** | Full | Study protocols, CRF templates, monitoring plan libraries | Web search enabled |
| **Regulatory Affairs** | Full | eCTD templates, FDA/EMA guidance, precedent correspondence | Document extraction *(structured data from regulatory letters)* |
| **Pharmacovigilance** | Advanced analysis only | MedDRA dictionaries, CIOMS forms, signal detection SOPs | RAG-only mode *(responses grounded in internal source documents)* |
| **Manufacturing / CMC** | Full | Batch records, process validation reports, equipment SOPs | File upload enabled |
| **Medical Affairs** | Full | Product monographs, congress abstracts, KOL slide decks | Web search enabled |
| **Support Staff** | Basic tasks only | Company policies, HR procedures, training materials | No file upload, no web search |

Groups synchronize with your identity provider (Okta, Azure AD, Ping Identity) via OAuth, so when someone transfers between departments, their AI permissions update on next login.

---

## The Infrastructure Behind It

*This section is a reference for your IT or infrastructure team. If you're evaluating at a strategic level, the key takeaway is: a self-hosted AI platform can deploy on existing infrastructure (VMware, Azure, AWS, or bare metal), scale horizontally, and can operate without external dependencies once models are loaded.*

For large pharma organizations (500-10,000+ employees), a production deployment typically requires high availability and data isolation. Here's a reference architecture using Open WebUI - for full deployment instructions, see the **[Technical Setup Guide](setup.md)**.

```mermaid
flowchart TB
    subgraph clients["Clients"]
        browser["Browser / PWA"]
    end

    subgraph proxy["Network Boundary"]
        lb["Reverse Proxy<br/>(Nginx / Traefik)<br/>TLS Termination"]
    end

    subgraph owui["Open WebUI Cluster"]
        owui1["Open WebUI<br/>Instances"]
    end

    subgraph data["Data Layer"]
        pg["PostgreSQL 16<br/>+ PGVector"]
        redis["Redis<br/>Sessions & WebSocket"]
        storage["Shared Storage<br/>(S3-compatible / NFS)"]
    end

    subgraph inference["LLM Inference Layer"]
        ollama["Ollama<br/>(Small Local Models)"]
        vllm["vLLM<br/>(Large Local Models)"]
    end

    subgraph optional["Optional Services"]
        functions["Functions<br/>(Built-in Plugins)"]
        otel["OpenTelemetry<br/>Collector"]
    end

    clients --> proxy
    proxy --> owui
    owui --> data
    owui --> inference
    owui -.-> optional
```

What makes this architecture relevant for pharma specifically:

- **Air-gappable.** When models are pre-loaded, the entire stack can run without outbound internet access. No prompts, completions, or embeddings leave your network when configured for local-only inference.
- **Separable by function.** RBAC and group-based document access mean R&D doesn't see PV data, PV doesn't see CMC data, and IT can manage the platform without viewing conversation content - all configurable at the application level.
- **Auditable.** Conversations are timestamped and attributed to authenticated users via SSO. Chat deletion and temporary chats can be disabled at the application level, creating records that your quality team can evaluate as part of their own governance framework.
- **Scalable without re-architecture.** Stateless application nodes scale horizontally. Add capacity during high-demand periods, scale back during quieter ones. Lose any single node without service interruption.

---

## What It Takes to Get There

Self-hosting AI is not trivial. Before committing, organizations should consider:

- **Validation effort.** If AI is used in GxP-adjacent workflows, the platform will likely need to go through your Computer System Validation process. This is an organizational responsibility, not something the software provides out of the box. Plan for IQ/OQ/PQ scoping, test case development, and documentation.
- **Infrastructure costs.** Open WebUI itself is free, but GPU servers, storage, and networking are not. A single-department pilot can run on one GPU server in your existing environment; a full production deployment involves dedicated compute and storage.
- **Governance design.** Who approves AI use cases? How are outputs reviewed? What's the policy for AI-assisted content in submissions? These questions matter more than the technology.
- **Ongoing maintenance.** Model updates, security patches, user support, and knowledge base curation are ongoing responsibilities. A pilot can typically be running within hours; a full production rollout typically takes a few weeks.

For organizations that want to explore the technical details, the complete Docker Compose stack, security hardening checklist, RBAC configuration guide, and backup strategy are in our companion guide:

**[Technical Setup Guide →](setup.md)**

For organizations that want deployment guidance, [Open WebUI Enterprise](https://docs.openwebui.com/enterprise/) offers hands-on support including regulatory alignment guidance *(compliance determination remains your organization's responsibility)*, white-label branding, and dedicated SLAs.

**[Learn more about Enterprise → sales@openwebui.com](mailto:sales@openwebui.com)**

---

### Disclaimer

*Open WebUI is a general-purpose AI platform. It is not a validated GxP system. All regulatory compliance determinations - including 21 CFR Part 11, EMA Annex 11, HIPAA, and any other applicable framework - are the sole responsibility of the deploying organization. AI-generated content is not a substitute for professional scientific, clinical, or regulatory judgment and must always be reviewed by qualified personnel before use.*

---

*Open WebUI is free to use and self-hostable. It powers AI deployments at organizations ranging from small research teams to Fortune 500 companies. [See who's using Open WebUI →](https://docs.openwebui.com/enterprise/customers/)*

---

### References

1. *"Samsung Bans ChatGPT Among Employees After Sensitive Code Leak."* Mashable, 2023. [mashable.com](https://mashable.com/article/samsung-chatgpt-leak-leads-to-employee-ban)
2. *"AI Data Security: The 83% Compliance Gap Facing Pharmaceutical Companies."* Contract Pharma / Kiteworks, 2024. [contractpharma.com](https://www.contractpharma.com/exclusives/ai-data-security-the-83-compliance-gap-facing-pharmaceutical-companies/)
3. *21 CFR Part 11 - Electronic Records; Electronic Signatures.* U.S. Food & Drug Administration. [ecfr.gov](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11)
4. *Annex 11: Computerised Systems.* European Commission, EudraLex Volume 4. [health.ec.europa.eu](https://health.ec.europa.eu/system/files/2016-11/annex11_01-2011_en_0.pdf)
