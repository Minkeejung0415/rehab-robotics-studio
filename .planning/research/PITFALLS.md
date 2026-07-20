# Pitfalls Research: Processing-Block Deployment Messages

**Domain:** Transporting executable source as ROS 2 data
**Researched:** 2026-07-20
**Confidence:** HIGH

## Critical Pitfalls

### 1. Treating a Hash as Authorization

**What goes wrong:** A future updater installs malicious but internally consistent code.

**Why:** SHA-256 detects alteration but does not identify or authorize the publisher.

**Avoidance:** In v1.2 call the field an integrity hash and never claim trust. Defer signatures, SROS2 identity, topic permissions, and updater allowlists explicitly.

**Warning signs:** UI labels such as “secure” or “trusted” based only on matching hashes.

### 2. Executing During Validation

**What goes wrong:** Loading or observing a custom block runs arbitrary code on the workstation.

**Avoidance:** Treat code as UTF-8 text. Parse YAML with a safe parser, validate structure, calculate hashes, and never import/eval/exec.

### 3. Nondeterministic Hashes

**What goes wrong:** Equivalent content generates different revisions because YAML ordering, line endings, timestamps, or update IDs differ.

**Avoidance:** Specify UTF-8, LF normalization policy, dependency ordering, canonical manifest serialization, and exactly which fields are hashed. Add golden-vector tests shared between TypeScript and Python.

### 4. Rosbridge QoS First-Advertiser Trap

**What goes wrong:** The finalized topic is volatile even though later code requests transient-local durability.

**Why:** rosbridge shares one publisher per topic and the first advertisement selects QoS.

**Avoidance:** Centralize publisher creation and advertise each topic once before publishing.

### 5. Confusing Generated With Installed

**What goes wrong:** Operator assumes Jetson processing changed when only a local message existed.

**Avoidance:** Use lifecycle states `draft`, `final`, and `validated_local`; reserve `received`, `staged`, `activated`, `rolled_back`, and `failed_remote` for the future updater protocol.

### 6. Unbounded Payloads

**What goes wrong:** Large source strings stall browser/rosbridge serialization or exceed WebSocket/server limits.

**Avoidance:** Enforce a documented v1.2 source/manifest size ceiling, show byte counts, and reject oversized final messages. Multi-file/archive transport remains deferred.

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Allow any ROS participant to publish updates | Future remote code injection | Future SROS2 authentication/access control and updater-side allowlist/signature policy. |
| Put private signing material in browser assets | Key theft | Signing belongs in a trusted deployment service, not v1.2. |
| Let YAML select arbitrary filesystem paths | Path traversal on future Jetson | Entrypoint is a logical basename; updater must stage into a controlled directory. |
| Install dependencies from message automatically | Supply-chain execution | Dependencies are declarative metadata only in v1.2. |

ROS 2 security is disabled by default; SROS2 provides PKI authentication, access control, and encryption, but those capabilities must be explicitly enabled and provisioned. Tailscale connectivity alone would not authorize deployment-topic publishers.

## “Looks Done But Isn’t” Checklist

- [ ] Custom type is discoverable by rosbridge in a clean sourced workspace.
- [ ] Draft fires only for valid direct source-to-processing edges.
- [ ] Deploy revalidates and does not reuse a stale draft object.
- [ ] Identical artifacts produce identical content hashes in TypeScript and Python.
- [ ] Modified code or manifest changes the hash.
- [ ] Invalid YAML, missing source, incompatible ports, and oversized payloads block final publication.
- [ ] Local status never reports Jetson installation.
- [ ] Code strings containing Unicode, quotes, and newlines survive rosbridge round-trip exactly.

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Contract drift / nondeterministic hash | Interface and artifact contract | Cross-language golden vectors. |
| Incorrect graph trigger | GUI artifact generation | Edge/connect/disconnect tests. |
| QoS and rosbridge mismatch | ROS publication | Late-subscriber and clean-workspace tests. |
| Accidental execution or false success | Local observer/verification | Static review and rejection/status tests. |

## Sources

- ROS 2 DDS security integration: https://design.ros2.org/articles/ros2_dds_security.html
- ROS 2 access control policies: https://design.ros2.org/articles/ros2_access_control_policies.html
- ROS 2 security deployment guidance: https://docs.ros.org/en/humble/Tutorials/Advanced/Security/Deployment-Guidelines.html
- rosbridge protocol/QoS limitations: https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md

---
*Pitfalls research for: v1.2 Block Deployment*

