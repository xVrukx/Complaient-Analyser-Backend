from typing import TypedDict, Optional
from groq import Groq
from langgraph.graph import START, END, StateGraph
from dotenv import load_dotenv
import os
import json
import psycopg
from psycopg.rows import dict_row


# ---------------------------------------------------------
# Environment
# ---------------------------------------------------------

load_dotenv()

GROQ_API_KEY = os.getenv("API")

Model = Groq(api_key=GROQ_API_KEY)


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

def get_db_connection():
    """
    Connect to Clever Cloud PostgreSQL.

    Clever Cloud automatically exposes these variables when
    the PostgreSQL add-on is linked to the application.
    """

    return psycopg.connect(
        host=os.getenv("POSTGRESQL_ADDON_HOST"),
        port=os.getenv("POSTGRESQL_ADDON_PORT"),
        dbname=os.getenv("POSTGRESQL_ADDON_DB"),
        user=os.getenv("POSTGRESQL_ADDON_USER"),
        password=os.getenv("POSTGRESQL_ADDON_PASSWORD"),
        row_factory=dict_row
    )


def initialize_database():
    """
    Create the complaint table if it doesn't already exist.
    """

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS complaints (
                    id SERIAL PRIMARY KEY,
                    response JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        connection.commit()

    finally:
        connection.close()


# ---------------------------------------------------------
# Database Functions
# ---------------------------------------------------------

def parse_ai_json(content: str) -> dict:
    content = content.strip()

    if content.startswith("```"):
        lines = content.splitlines()

        # Remove ```json or ```
        lines = lines[1:]

        # Remove closing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        content = "\n".join(lines).strip()

    try:
        return json.loads(content)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"AI returned invalid JSON: {content}"
        )

def get_complaint(complaint_id: int):
    """
    Fetch an existing complaint from SQL.
    """

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT id, response, created_at, updated_at
                FROM complaints
                WHERE id = %s
                """,
                (complaint_id,)
            )

            return cursor.fetchone()

    finally:
        connection.close()


def add_complaint(response: dict):
    """
    Insert a new complaint.
    """

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO complaints (response)
                VALUES (%s)
                RETURNING id, response, created_at, updated_at
                """,
                (json.dumps(response),)
            )

            result = cursor.fetchone()

        connection.commit()

        return result

    finally:
        connection.close()


def update_complaint(complaint_id: int, response: dict):
    """
    Update an existing complaint.
    """

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE complaints
                SET
                    response = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, response, created_at, updated_at
                """,
                (
                    json.dumps(response),
                    complaint_id
                )
            )

            result = cursor.fetchone()

        connection.commit()

        return result

    finally:
        connection.close()


# ---------------------------------------------------------
# LangGraph State
# ---------------------------------------------------------

class State(TypedDict):
    complaient: str
    response: dict
    update: bool

    # Existing data loaded from SQL during update.
    refined_data: dict

    # ID of the complaint being updated.
    complaint_id: Optional[int]


# ---------------------------------------------------------
# Nodes
# ---------------------------------------------------------

def Initliser(state: State):

    print("Starting the process")

    return {}


def Route1(state: State):
    """
    Decide Add or Update.

    The frontend does not decide the operation.

    The backend determines this before invoking the graph
    by checking whether the supplied complaint ID exists.
    """

    if state["update"]:
        return "Update"

    return "Add"


def AddComplaient(state: State):

    completion = Model.chat.completions.create(
        model="llama-3.3-70b-versatile",

        messages=[
            {
                "role": "system",
                "content": """
You are a customer complaint extraction system.

Extract information from the user's complaint and return
ONLY valid JSON.

The JSON must have exactly these top-level sections:

{
    "ProductDetails": {},
    "ComplaintDetails": {
        "ComplaintCategory": "",
        "ComplaintDescription": ""
    },
    "AIAssessment": {
        "SuggestedSeverity": "",
        "SuggestedNextAction": "",
        "InitialRiskAssessment": ""
    }
}

ProductDetails is dynamic.

Determine the relevant product fields from the complaint.
For example:
Brand, Model, Product Name, Batch Number,
Manufacturing Date, Expiry Date, Serial Number, etc.

If an important product field is explicitly required but
the user has not provided its value, use "-".

Do not add explanations outside JSON.
"""
            },
            {
                "role": "user",
                "content": f"""
This is the customer complaint:

{state["complaient"]}
"""
            }
        ],

        temperature=0,
        max_completion_tokens=2048,
        top_p=1,
        stream=False
    )

    content = completion.choices[0].message.content

    response_json = parse_ai_json(content)

    state["response"] = response_json

    return {
        "response": response_json
    }


def UpdateComplaient(state: State):

    previous_data = state["refined_data"]

    completion = Model.chat.completions.create(
                model="llama-3.3-70b-versatile",

        messages=[
            {
                "role": "system",
                "content": """
You are updating an existing customer complaint record.

The existing complaint data is provided to you.

The new user information may:

1. Correct an existing value.
2. Add a new value.
3. Add new product fields.
4. Add more complaint information.
5. Change the AI assessment if the new information
   changes the severity, risk, or recommended action.

Rules:

- Preserve all valid existing information.
- Change only fields affected by the new information.
- Add new fields when new information is provided.
- Never remove valid existing information.
- Recalculate AIAssessment when the new information
  changes the complaint risk or severity.
- Keep the same top-level structure.
- ProductDetails may contain dynamic fields.

Return ONLY valid JSON.

The output must contain:

{
    "ProductDetails": {},
    "ComplaintDetails": {},
    "AIAssessment": {}
}
"""
            },

            {
                "role": "assistant",
                "content": json.dumps(previous_data)
            },

            {
                "role": "user",
                "content": f"""
Update the complaint using this new information:

{state["complaient"]}
"""
            }
        ],

        temperature=0,
        max_completion_tokens=2048,
        top_p=1,
        stream=False
    )

    content = completion.choices[0].message.content

    updated_json = parse_ai_json(content)

    state["response"] = updated_json

    return {
        "response": updated_json
}


# ---------------------------------------------------------
# Graph
# ---------------------------------------------------------

sgraph = StateGraph(State)

sgraph.add_node("Init", Initliser)
sgraph.add_node("Add", AddComplaient)
sgraph.add_node("Update", UpdateComplaient)

sgraph.add_edge(START, "Init")

sgraph.add_conditional_edges(
    "Init",
    Route1
)

sgraph.add_edge("Add", END)
sgraph.add_edge("Update", END)

agentWrap = sgraph.compile()


# ---------------------------------------------------------
# Main Agent Function
# ---------------------------------------------------------

def Agent(
    complaient: str,
    complaint_id: Optional[int] = None
):
    """
    Main backend entry point.

    complaint_id=None
        -> Add

    complaint_id=<existing ID>
        -> Update
    """

    # -----------------------------------------------------
    # ADD
    # -----------------------------------------------------

    if complaint_id is None:

        graph_state: State = {
            "complaient": complaient,
            "response": {},
            "update": False,
            "refined_data": {},
            "complaint_id": None
        }

        result = agentWrap.invoke(graph_state)

        # Save generated data to SQL first.
        saved_record = add_complaint(
            result["response"]
        )

        return saved_record

    # -----------------------------------------------------
    # UPDATE
    # -----------------------------------------------------

    existing_record = get_complaint(complaint_id)

    if existing_record is None:

        raise ValueError(
            f"Complaint with ID {complaint_id} does not exist."
        )

    previous_data = existing_record["response"]

    graph_state: State = {
        "complaient": complaient,
        "response": {},
        "update": True,
        "refined_data": previous_data,
        "complaint_id": complaint_id
    }

    result = agentWrap.invoke(graph_state)

    # Save the updated data.
    saved_record = update_complaint(
        complaint_id,
        result["response"]
    )

    return saved_record
