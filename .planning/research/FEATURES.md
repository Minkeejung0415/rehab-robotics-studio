# Feature Research: Processing-Block Deployment Messages

**Domain:** Visual graph to ROS 2 deployment-artifact generation
**Researched:** 2026-07-20
**Confidence:** HIGH

## Feature Landscape

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Explicit typed contract | Future updater must not guess field meanings | MEDIUM | Dedicated ROS interface package. |
| Deterministic identity and revision | Drafts and deployments need correlation and deduplication | MEDIUM | Include update ID, graph ID, block ID, artifact revision, schema version. |
| Exact code and manifest payload | Jetson updater ultimately needs reproducible input | MEDIUM | One language-neutral UTF-8 entry file plus YAML. |
| Integrity verification | Code must not change unnoticed in transport or serialization | MEDIUM | SHA-256 over a documented canonical byte sequence. |
| Graph-aware trigger | Only deploy processors actually attached to a source | MEDIUM | Require a valid direct source-output to processor-input edge. |
| Draft/final distinction | Editing should not silently become a release | LOW | `draft` on connect; `final` only on Deploy. |
| Actionable validation | Missing code, manifest, language, entrypoint, or incompatible ports must block finalization | MEDIUM | Surface block-specific errors in GUI and observer status. |
| Local inspection | The milestone must work without Jetson | LOW | ROS CLI echo plus observer tests. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Canonical reproducible payload | Same graph artifact produces the same hash | MEDIUM | Exclude timestamps/update IDs from content hash. |
| Source context snapshot | Future updater can validate input signal assumptions | MEDIUM | Include source type, port, signal type, units/rate when known. |
| Status correlation | Operator can match validation output to the message | MEDIUM | Status includes update ID and content hash. |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Execute uploaded code locally | Fast demo of processing | Turns message generation into arbitrary-code execution | Validate text and metadata only. |
| Auto-finalize on every wire edit | Immediate synchronization | Makes accidental wiring a deployment event | Publish drafts automatically; final only on Deploy. |
| Claim remote success | Makes UI look complete | Jetson is absent; no updater acknowledgment exists | Report `generated`/`validated_local`, never `installed`. |
| Bundle an entire folder | Handles complex projects | Adds archive traversal, size, dependency, and security concerns | Single entry file for v1.2. |

## Feature Dependencies

```text
Typed ROS interface
  -> artifact serializer
      -> draft-on-connect publisher
      -> final-on-Deploy publisher
          -> local observer and contract tests

Custom block artifact loading
  -> manifest/code validation
      -> deterministic hash
```

## MVP Definition for v1.2

- [ ] Load or represent a deployable processor artifact with YAML and one source file.
- [ ] Generate one typed draft message for each valid direct source-to-processor attachment.
- [ ] Publish finalized messages only from Deploy after validation.
- [ ] Inspect and validate messages locally without code execution.
- [ ] Verify schema fields, trigger semantics, hash stability, and rejection cases in automated tests.

## Deferred

- Tailscale or WAN transport configuration.
- Jetson updater subscription, staging, rollback, process restart, and acknowledgment.
- Signatures/trust policy beyond SHA-256 integrity.
- Multi-file packages, binary artifacts, containers, and dependency installation.

## Sources

- ROS custom interface tutorial: https://docs.ros.org/en/iron/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.html
- rosbridge typed advertise/publish behavior: https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md
- ROS 2 QoS compatibility and late subscribers: https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html

---
*Feature research for: v1.2 Block Deployment*

