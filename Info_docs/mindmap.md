# Hierarchical Mindmap

## 1. Structural Overview
The mindmap details the vast scale and modular architecture of SovereignAI Edge. Because the platform acts as a monolith, mapping out its components visualizes responsibilities from the presentation layer down to OS-level tensor execution.

## 2. Detailed Mindmap Visual Structure
```mermaid
mindmap
    root((SovereignAI Edge))
        UI["UI Interfaces"]
            React["React Web App"]
            Electron["Desktop Wrapper"]
            CLI["Python CLI"]
        API["Backend API"]
            FastAPI["FastAPI App"]
            WS["Websocket Mgr"]
            Tasks["Background Tasks"]
        Core["Core Logic"]
            LlamaCPP["Llama.cpp Bindings"]
            LayerStream["LayerStream Core"]
            Plugins["Plugin Registry"]
            State["State Manager"]
        Storage["Storage"]
            Models["/models"]
            Database["/database"]
            PluginDir["/plugins"]
        Security["Security"]
            Hardware["Hardware Bounds"]
            Sandboxing["OS Sandboxing"]
            Privacy["Data Privacy"]
```

