# Wildcat Seed/Key Research Report

**Scope:** Legitimate sources only. No reverse engineering, no firmware extraction, no UnlockECU concrete algorithms, no bruteforcer, no leaked/cracked material. Research conducted 2026-11-01 by the Wildcat seed/key research team (3 subagents) under Aria's lead.

## 1. Organization

- **Lead:** Aria (code owner, report author).
- **Researchers (subagents):**
  - R1 — publicly documented / openly licensed seed/key algorithms.
  - R2 — legitimate OEM routes (portals, developer programs, licensed providers, costs/terms).
  - R3 — standards (ISO 14229-1, ISO 14230-2, SAE J2534) and open-source frameworks (OpenDiag, FreeDiag, pyOBD, udsoncan).
- No Kanban changes made (subagents only, per Vesper's direction).
- No code changes made — plug-in stays empty by default.

## 2. Findings: Standards

| Standard | Seed/key in standard? | Source | License |
|---|---|---|---|
| ISO 14229-1 (UDS) | No — defines only the 0x27 challenge-response protocol; algorithm is OEM-defined. | https://plaxidityx.com/blog/standards-and-compliance/iso-14229-12013-unified-diagnostic-services-uds/ | Copyrighted ISO standard |
| ISO 14230-2 (KWP2000) | No — seed/key calculation defined by vehicle manufacturer/system supplier. | https://studylib.net/doc/26169047/iso-14230-uds | Copyrighted ISO standard |
| SAE J2534 (PassThru) | No — tool-to-vehicle interface standard; security access performed via protocol messages. | https://www.sae.org/standards/content/j2534_201907/ | SAE copyrighted standard |

## 3. Findings: Open-Source Frameworks

| Framework | Ships seed/key algorithms? | Source | License |
|---|---|---|---|
| OpenDiag | No — general OBD-II/UDS diagnostic CLIs. | https://github.com/maximus64/opendiag-cli | Not clearly stated |
| FreeDiag | No — OBD-II/KWP protocol suite; community examples are separate. | https://sourceforge.net/projects/freediag/ | GPL (verify version) |
| pyOBD / python-OBD | No — OBD-II PIDs and serial communication. | https://github.com/peterh/pyobd | Verify in repo |
| udsoncan | No — security access supported but key algorithm must be supplied by user. | Referenced in automotive diagnostics material | Verify in repo |

## 4. Findings: Open-Source Repositories (Provenance Unverified)

These are publicly available implementations. Their provenance (whether OEM-licensed, reverse-engineered, or community-derived) is **not verified**. They are listed for reference only and are **NOT** implemented in Wildcat pending provenance verification.

| Repo | Algorithm | License | Provenance status |
|---|---|---|---|
| Xaloqi/EDS | AES-128-CMAC + TRNG for SID 0x27 | GPL-2.0 | Third-party EDS reference implementation; not an OEM-published algorithm |
| ludwig-v/psa-seedkey-algorithm | PSA/Stellantis seed/key | GPL-3.0 | Community-published; provenance unverified (likely reverse-engineered) |
| bri3d/sa2_seed_key | VW SA2 seed/key | (check repo) | Community-published; provenance unverified |
| hjtrbo/GM-Security-Tester | GM E38 seed/key | (check repo) | Community-published; provenance unverified |

**Exclusion note:** Per Vesper's direction, none of these are ported. They are listed so Zach can evaluate whether any has a legitimate licensing path. Wildcat's plug-in stays empty by default.

## 5. Findings: Legitimate OEM Routes

| Manufacturer | Portal / Program | Diagnostic software | Seed/key access | Cost (where published) | Terms |
|---|---|---|---|---|---|
| Mercedes-Benz | B2B Connect (b2bconnect.mercedes-benz.com) — XENTRY WIS/ISP/Parts | XENTRY (dealer-level); independent workshop via B2B Connect | XENTRY embeds seed/key; extended Seed & Key procedure (per Bosch Esitronic). Security data via NASTF SDRM (US). | Not publicly listed for seed/key specifically | Subscription via B2B Connect |
| BMW | BMW ISTA / TIS | ISTA | Embedded in ISTA diagnostic workflow | Not publicly listed | Dealer/independent workshop subscription |
| Ford | Ford FDRS / IDS | FDRS/IDS | Embedded in diagnostic software | Not publicly listed | Subscription |
| VW/Audi | ODIS (Offboard Diagnostic Information System) | ODIS | Embedded in diagnostic software | Not publicly listed | Subscription |
| JLR | JLR TOPIx / SDD | SDD/Pathfinder | Embedded in diagnostic software | Not publicly listed | Subscription |
| Volvo | Volvo Tech Info (volvotechinfo.com) — VIDA | VIDA | VGM requires VIDA subscription with software download | 3-day $73.14, 30-day $648.22, 365-day $7,547.76 (NA, with software download); parts/service/diagnostics-only tiers cheaper | Independent operators need dealer contact for software |
| Honda | Honda Service Express / HDS | HDS | Embedded in HDS | Not publicly listed | Subscription |
| Subaru | Subaru Tech Info / SSM | SSM | Embedded in SSM | Not publicly listed | Subscription |

## 6. Third-Party Licensed Tools (Seed/Key Embedded)

| Tool | Coverage | Cost | Terms |
|---|---|---|---|
| Autel (IMMO/MaxiSys) | Multi-brand, key programming/IMMO | Hardware $1,500–$4,000+; subscription for updates | Embedded in hardware/software; requires NASTF VSP (US) |
| Launch X431 | Multi-brand diagnostics, key programming, IMMO | Device $1,500–$4,000; subscription device-bound | Embedded; cloud-based OEM auth tokens |
| Bosch KTS/Esitronic | Multi-brand including Mercedes security gateway | Hardware + subscription; ~$600/yr for Mercedes CAN FD | Subscription; hardware-bound |

## 7. Classification Per ECU Family

- **Obtainable legitimately:** Only via OEM diagnostic software subscriptions or licensed third-party tools (above). No open/public algorithm available for any manufacturer.
- **Proprietary-only / licence-required:** All production seed/key algorithms for all manufacturers researched (Mercedes, BMW, Ford, VW/Audi, JLR, Volvo, Honda, Subaru, GM, PSA, etc.).
- **Unknown:** Any ECU family not covered by the OEM routes above; no public documentation found.

## 8. Licensing Routes for Wildcat

- **OEM diagnostic software** (XENTRY, ISTA, FDRS, ODIS, etc.): Subscription grants use of the software, not redistribution rights. Wildcat cannot ship OEM seed/key algorithms under these terms — they are embedded in licensed software, not licensed for redistribution.
- **Third-party tools** (Autel, Launch, Bosch): Device-bound, cloud-authenticated. No redistribution rights.
- **NASTF SDRM (US):** Security data for locksmiths/professionals; requires VSP (Verified Security Professional) credential. Not a redistribution license.
- **ISO/SAE standards:** Define protocol only; no algorithms. Purchase required; not redistributable.
- **Conclusion:** No licensing route found that would allow Wildcat to ship a production seed/key algorithm. The plug-in interface remains the correct design — a user with legitimate access can supply their own algorithm.

## 9. Deliverable Status

- **Code changes:** None. Plug-in (`SecurityAlgorithmRegistry`) stays empty by default; `NoAlgorithmConfiguredError` raised when unconfigured. No fabricated keys.
- **Report file:** `docs/seed_key_research.md` (this file).
- **Tests:** No new tests (no code changed). Full suite remains 174 passed; ruff clean.
- **Skipped:** Implementation of any concrete algorithm — reason: no legitimately documented algorithm with clear provenance found; all available implementations have unverified provenance.

## 10. Exclusions Honored

- No reverse engineering of OEM algorithms.
- No firmware extraction.
- No porting of UnlockECU's concrete algorithms.
- No bruteforcer built or used.
- No leaked/cracked material used.
- No 0x27/0x29 wire protocol changes.
- No Hermes channel/setting changes.
- No messages to anyone else.
EOF
echo "written"