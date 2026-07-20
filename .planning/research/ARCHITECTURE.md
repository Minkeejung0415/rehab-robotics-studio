# Architecture Research: Processing-Block Deployment Messages

**Domain:** Browser graph artifact publication to ROS 2
**Researched:** 2026-07-20
**Confidence:** HIGH

## Recommended Architecture

```text
Custom block folder                     Canvas graph
block.json + processor.yaml + code      source -> processor edge
             |                                  |
             +----------> Artifact builder <----+
                               |
                    validate + canonicalize
                    hash manifest + code
                               |
                 +-------------+-------------+
                 |                           |
          edge connected                 Deploy pressed
                 |                           |
       /processing_blocks/draft    /processing_blocks/update
                 |                           |
                 +---------- rosbridge ------+
                               |
                    typed ROS 2 interface
                               |
                     local observer only
                    validate, never execute
                               |
                /processing_blocks/status

Future: finalized topic -> Tailscale-visible ROS boundary -> Jetson updater
```

## Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| Block artifact loader | Read block definition, manifest YAML, and one entry source file; retain text in registry state. |
| Graph attachment selector | Identify valid direct edges whose source block is acquisition-class and target is deployable processing-class. |
| Artifact builder | Construct one immutable, schema-versioned update object and canonical content hash. |
| Draft publisher | Publish after a valid connection or artifact-affecting edit; never imply installation. |
| Deploy publisher | Revalidate the current graph and publish finalized artifacts in deterministic graph order. |
| ROS interface package | Define the cross-machine contract independently from GUI and updater implementation. |
| Local observer | Recalculate hash, validate required fields/YAML, publish status, and retain no execution capability. |

## Proposed `ProcessingBlockUpdate.msg`

```text
std_msgs/Header header
string schema_version
string update_id
string lifecycle_stage          # draft | final
string graph_id
string source_block_id
string source_block_type
string source_port_id
string source_signal_type
string processor_block_id
string processor_block_type
string processor_revision
string language
string entrypoint
string manifest_yaml
string source_code
string[] dependencies
string content_sha256
```

The field names are a research recommendation, not yet an implementation commitment. The content hash should cover schema version, source/processor identity relevant to execution, normalized manifest, entrypoint, language, dependencies, and exact UTF-8 source bytes. It should exclude `header.stamp` and random `update_id` so identical content hashes identically.

## Key Patterns

### Contract Before Transport

Define and test the interface plus canonical hash before adding any Tailscale/Jetson logic. This keeps future networking from changing payload semantics.

### Two-Stage Event Model

Draft is an editing event. Final is an operator intent event. The same builder handles both and changes only lifecycle metadata/update ID after revalidation.

### Immutable Snapshot

Messages contain a snapshot, not a path into browser state. A later edit produces a new revision/hash; previously observed messages remain understandable.

### Fail Closed for Final

An invalid artifact may produce a visible draft error/status but must not produce a final update. Deploy reports which block prevented publication.

## Integration Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Graph store -> deployment builder | Typed in-process function | Avoid ROS details in generic graph mutation code. |
| Deployment builder -> rosbridge | Typed serializer | Advertise custom type once with intentional QoS. |
| rosbridge -> ROS graph | Custom topic | Type must be installed in the same sourced workspace as rosbridge. |
| Update topic -> local observer | `rclpy` subscription | Observer validates only; future updater is a separate node. |

## Sources

- ROSIDL-generated type support: https://docs.ros.org/en/humble/Concepts/About-Internal-Interfaces.html
- Custom interface package structure: https://docs.ros.org/en/iron/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.html
- rosbridge QoS and typed messages: https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md
- ROS 2 QoS durability: https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html

---
*Architecture research for: v1.2 Block Deployment*

