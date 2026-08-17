# Concept
Build is a AI agent that has **Add**, **Update**, and **Document Extraction** features (Document Extraction defaults to Add).

The fields will be dynamic based on the complaint, meaning both the field names and labels will be generated dynamically by the AI.

# Flow Structure
The Agent will produce three sections:

- Product Details
- Complaint Details
- AI Complaint Assessment

Each feature will have a separate node.

### Add feature

- **Product Details**
  - Contains all product-related information extracted from the complaint.

- **Complaint Details**
  - Complaint Category
  - Complaint Description

- **AI Assessment**
  - Suggested Severity
  - Suggested Next Action
  - Initial Risk Assessment

### Update feature

The frontend sends the **Complaint ID** along with the additional or corrected complaint information.

The backend retrieves the existing structured complaint data from the SQL database using the Complaint ID before invoking the graph.

The AI updates only the required fields, preserves existing valid information, and adds new information if it was not previously available for:

- ProductDetails
- ComplaintDetails
- AIAssessment

### Document Extraction feature

Extract the text from the PDF before entering the graph.

# State for graph

```python
class state{
    RawData: str
    RefinedData: {
        ProductDetails:{fields},

        ComplaintDetails:{
            complaintCategory:,
            complaintDescription:
        },

        AiAssessment:{
            Severity:,
            suggestedNextAction:,
            initialRiskAssessment:
        }
    }

    update: bool
}
```

# Nodes

```python
def NodeIdentifier(state){
    if RefinedData is empty:
        update = false
    else:
        update = true
}
```

```python
def AddrefinedData(state){
    ai request with instruction and raw data
    ai response update RefinedData state
    return RefinedData key from state
}
```

```python
def UpdaterefinedData(state){
    ai request with instruction, raw data, RefinedData key from state
    ai response update only values that are meant to be updated for RefinedData
    return RefinedData key from state
}
```

# Router

```python
def UpdateOrAdd(state){
    decides whether to run AddRefinedData or UpdateRefinedData
    based on the update key
}
```

# Edges

```python
sg = StateGraph(state)

sg.add_edge(START, "NodeIdentifier")

sg.add_conditional_edges(
    "NodeIdentifier",
    UpdateOrAdd
)

sg.add_edge("AddrefinedData", END)

sg.add_edge("UpdaterefinedData", END)
```

# Input function

Accepts data in PDF or text format.

- If input is a PDF, extract the text.
- If a Complaint ID is provided, retrieve the existing structured complaint from the SQL database and populate `RefinedData`.
- Otherwise, initialize `RefinedData` as empty.
- Populate `RawData`.
- Invoke the graph.
- Save the graph output to the SQL database.
- Return the saved record to the frontend using its Complaint ID.

# File Structure

```text
Avioa
|----backend/
|   |-------server.py      # Connects routes with the input function.
|   |-------Route.py       # Handles API routes for text and PDF requests.
|   |-------AiAgent.py     # Main graph and AI logic.
|   |-------.env
|   |-------.gitignore
|   |-------Document.md
|
|----Frontend/
|   |-------Src/
|          |------app.jsx
|          |------index.jsx
```

Only important files and folders are included.

# After process

After the graph finishes processing:

1. The backend saves the generated or updated structured complaint to the SQL database.
2. The backend retrieves the saved record using its Complaint ID.
3. The saved record is returned to the frontend.
4. The frontend displays the returned data.