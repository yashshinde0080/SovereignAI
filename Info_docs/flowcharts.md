# Process Flowcharts

## 1. Request Handling Flowchart
The following logic tree illustrates how SovereignAI Edge parses incoming commands, handles errors, and executes models in strictly ==offline== environments. 

## 2. Model Initialization Flowchart Visual
```mermaid
graph TD
    Start([User Request: Load Model]) --> CheckModel{Is Model File Present?}
    CheckModel -- No --> Error[Throw 404 Error UI]
    CheckModel -- Yes --> ReadHeader[Read [[GGUF]] Header]
    ReadHeader --> CalcFootprint[Calculate Compute Footprint]
    CalcFootprint --> Compare[Compare w/ System Specs]
    Compare --> Decision{Fits in RAM?}
    Decision -- Yes --> FullLoad[Llama.cpp Full Load]
    Decision -- No --> LayerStream[Initialize [[LayerStream]]]
```

## 3. Request Error Handling Flowchart Visual
```mermaid
graph TD
    Start([Incoming Chat Payload]) --> Validate{[[Pydantic]] Validation}
    Validate -- Invalid --> Return422[Return 422 Error]
    Validate -- Valid --> PreProcess[Pre-processing Pipeline]
    PreProcess --> BusyCheck{Is Engine Busy?}
    BusyCheck -- Yes --> Enqueue[Enqueue Job & Send 202]
    BusyCheck -- No --> Inference[Trigger Inference]
    Inference --> Stream[Stream Response]
```

## See Also
- [[Working]] — State machine and core operational states
- [[Engines Overview]] — FullRAM and LayerStream engine architecture
- [[Technical Architecture]] — System components and deployment
