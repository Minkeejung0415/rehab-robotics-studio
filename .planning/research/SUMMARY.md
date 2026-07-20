# Project Research Summary: Processing-Block Deployment Messages

**Project:** Rehab Robotics Studio
**Domain:** Browser-authored ROS 2 processing-block deployment contracts
**Researched:** 2026-07-20
**Confidence:** HIGH

## Executive Summary

The safest v1.2 is a contract-first milestone. A dedicated ROS 2 interface package should define one typed `ProcessingBlockUpdate` snapshot containing manifest YAML, a single language-neutral UTF-8 source file, graph/source/processor identity, revision information, declared dependencies, and a SHA-256 integrity hash. The browser can publish this type through the existing rosbridge connection, while a local Python observer validates the same contract without executing code.

The graph has two distinct boundaries: a valid direct source-to-processing connection creates a draft, while the existing Deploy action revalidates and publishes a final update. This preserves immediate authoring feedback without treating a canvas edit as permission to modify a Jetson. The final topic should be reliable and transient-local for local late-subscriber inspection, with the limitation that DDS durability is not a permanent remote outbox and only persists while the publisher remains alive.

The main risk is mistaking data integrity for deployment security. SHA-256 detects payload changes but does not authorize a publisher. Tailscale delivery, SROS2 identity/access control, signatures, Jetson staging/activation/rollback, and remote acknowledgments remain explicit future work. v1.2 statuses must say generated or locally validated, never installed.

## Key Findings

### Recommended Stack

- New `ament_cmake` package: `rehab_robotics_interfaces` with `ProcessingBlockUpdate.msg`.
- Existing `rehab_robotics_bridge`: local `rclpy` observer/validator only.
- Existing React/TypeScript graph: artifact loading, deterministic serializer, Web Crypto SHA-256, and rosbridge publication.
- YAML 2.x parser/serializer for safe validation and canonical manifest output.

### Must-Have Features

- Typed, schema-versioned, immutable update snapshot.
- Draft-on-connect and final-on-Deploy semantics.
- Direct source-to-processing graph validation.
- Manifest/code/dependency metadata and deterministic content hash.
- Payload size ceiling and actionable block-level validation errors.
- Local ROS echo/observer plus TypeScript/Python golden-vector tests.
- No local code execution and no false remote-success state.

### Architecture

1. Load a deployable artifact from a custom processing block.
2. Select valid direct source-to-processor attachments.
3. Canonicalize and hash the artifact into a typed snapshot.
4. Publish drafts or finals through separately advertised rosbridge topics.
5. Validate locally in a ROS Python observer that cannot execute the payload.

## Suggested Roadmap Shape

### Phase 9: Interface and Artifact Contract

Define the ROS message, manifest requirements, canonical hashing rules, fixtures, and contract tests before wiring UI events.

### Phase 10: Graph Artifact Generation

Retain code/YAML in the custom-block registry, identify source-to-processor attachments, generate drafts, and report validation errors.

### Phase 11: Final Publication and Local Verification

Integrate Deploy, publish typed final messages with intentional QoS, add the observer/status path, and verify rosbridge round-trips and non-execution.

## Confidence and Gaps

| Area | Confidence | Notes |
|------|------------|-------|
| ROS interface packaging | HIGH | Official ROSIDL/custom-interface documentation. |
| rosbridge typed publication | HIGH | Current protocol documents type validation and QoS objects. |
| Graph integration | HIGH | Existing code already exposes edge and Deploy actions. |
| Permanent offline delivery | LOW / deferred | Transient-local is not a disk-backed outbox; future Jetson transport needs a separate design. |
| Remote execution security | LOW / deferred | Requires signatures/trust, SROS2 policy, staging, rollback, and acknowledgments. |

## Primary Sources

- https://docs.ros.org/en/iron/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.html
- https://docs.ros.org/en/humble/Concepts/About-Internal-Interfaces.html
- https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html
- https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md
- https://design.ros2.org/articles/ros2_dds_security.html
- https://design.ros2.org/articles/ros2_access_control_policies.html
- https://docs.ros.org/en/humble/Tutorials/Advanced/Security/Deployment-Guidelines.html

---
*Research completed: 2026-07-20*
*Ready for requirements: yes*
