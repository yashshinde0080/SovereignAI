# Process Flowcharts

## 1. Request Handling Flowchart
The following logic tree illustrates how SovereignAI Edge parses incoming commands, handles errors, and executes models in strictly offline environments. 

## 2. Model Initialization Flowchart Visual
```text
           [ User Request: Load Model ]
                        |
            +-----------v-----------+
            | Is Model File Present |
            | in ./models folder?   |
            +-----+-----------+-----+
                  |           | (No)
            (Yes) |           v
                  |     +-----------+
                  |     | Throw 404 |
                  |     | Error UI  |
                  |     +-----------+
            +-----v-----+
            | Read GGUF |
            | Header    |
            +-----+-----+
                  |
        +---------v---------+
        | Calculate Compute |
        | Footprint (VRAM)  |
        +---------+---------+
                  |
        +---------v---------+
        | Compare w/ System | <--- (psutil/pyNVML)
        +----+---------+----+
             |         |
 (Fits in RAM)         (Too Large for RAM)
       +-----v----+    +-----v---------+
       | Llama.cpp|    | Initialize    |
       | Full Load|    | LayerStream   |
       +----------+    +---------------+
```

## 3. Request Error Handling Flowchart Visual
```text
             [ Incoming Chat Payload ]
                        |
            +-----------v-----------+
            |  Pydantic Validation  |
            +-----+-----------+-----+
                  |           |
        (Invalid) |           | (Valid)
            +-----v-----+     v 
            | Return 422|     [ Pre-processing Pipeline ]
            | (Bad Reg) |           |
            +-----------+     +-----v-----+
                              | Is Engine |
                              | Busy?     |
                              +--+-----+--+
                                 |     | (No)
                           (Yes) |     v
                                 |  [ Trigger Inference ]
                         +-------v-------+      |
                         | Enqueue Job & |      v
                         | Send 202 Stat |  [ Stream Response ]
                         +---------------+
```
