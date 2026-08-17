from flask import Blueprint, request, jsonify

from AiAgent import Agent


route = Blueprint("route", __name__)


@route.route("/complaint", methods=["POST"])
def complaint():

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "error": "Request body is required."
            }), 400

        complaient = data.get("complaient")
        complaint_id = data.get("update")

        # ---------------------------------------------
        # Validation
        # ---------------------------------------------

        if not complaient:
            return jsonify({
                "error": "complaient is required."
            }), 400

        # Convert empty/null update to None.
        if complaint_id in ("", None):
            complaint_id = None

        else:
            try:
                complaint_id = int(complaint_id)

            except ValueError:
                return jsonify({
                    "error": "update must be a valid complaint ID."
                }), 400

        # ---------------------------------------------
        # Run AI Agent
        # ---------------------------------------------

        result = Agent(
            complaient=complaient,
            complaint_id=complaint_id
        )

        return jsonify({
            "id": result["id"],
            "response": result["response"],
            "created_at": result["created_at"],
            "updated_at": result["updated_at"]
        }), 200

    except ValueError as error:

        return jsonify({
            "error": str(error)
        }), 404

    except Exception as error:

        print(error)

        return jsonify({
            "error": "Internal server error."
        }), 500