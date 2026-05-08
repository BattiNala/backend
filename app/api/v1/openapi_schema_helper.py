"""
OpenAPI schema definitions
"""

import json

from app.schemas.issue import (
    AnonymousIssueCreate,
    IssueCreate,
)

anon_issue_example = AnonymousIssueCreate.model_config.get("json_schema_extra", {}).get(
    "example", {}
)
issue_create_example = IssueCreate.model_config.get("json_schema_extra", {}).get("example", {})

OPENAPI_ANON_ISSUE_SCHEMA = {
    "requestBody": {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "photos": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                            "description": "List of photo files to upload.",
                        },
                        "issue_create": {
                            "type": "string",
                            "description": "JSON string for anonymous issue creation."
                            " Should match the AnonymousIssueCreate schema.",
                            "example": json.dumps(
                                AnonymousIssueCreate.model_config["json_schema_extra"]["example"]
                            ),
                        },
                    },
                    "required": ["photos", "issue_create"],
                }
            }
        }
    }
}

OPENAPI_ISSUE_CREATE_SCHEMA = {
    "requestBody": {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "photos": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                            "description": "List of photo files to upload.",
                        },
                        "issue_create": {
                            "type": "string",
                            "description": (
                                "JSON string for issue creation. "
                                "Should match the IssueCreate schema."
                            ),
                            "example": json.dumps(
                                IssueCreate.model_config["json_schema_extra"]["example"]
                            ),
                        },
                    },
                    "required": ["photos", "issue_create"],
                }
            }
        }
    }
}
