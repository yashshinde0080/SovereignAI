# SQLite

A ==serverless==, zero-configuration relational database engine embedded directly into applications. It stores data in a single file on disk.

## Role in SovereignAI Edge

[[SQLite]] is the ==primary local database== for SovereignAI Edge, storing all persistent data without requiring any database server:

- **Chat History:** All conversation messages and sessions
- **Model Registry:** Available models, their paths, and configurations
- **Plugin States:** Enabled/disabled plugins and their settings
- **Hardware Profiles:** Cached hardware detection results
- **User Settings:** UI preferences and application configuration

## Key Advantages for Local AI

- **Zero Dependencies:** No separate database server to install or maintain
- **Portable:** Single `.db` file can be moved with the application on a USB drive
- **Reliable:** ACID-compliant with crash recovery
- **Low Overhead:** Minimal memory footprint (~250KB)

## See Also

- [[TRD]] — Technical requirements and stack details
- [[PRD]] — Product vision and feature list
- [[Schedulers]] — Background database compaction tasks
