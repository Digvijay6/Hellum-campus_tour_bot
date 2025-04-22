from openai import AzureOpenAI
from app.utils import AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, DEPLOYMENT_NAME


class AzureGPT:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version="2024-05-01-preview",
        )

    def get_tool_response(self, messages: list):
        """This function integrates tool calling."""
        try:
            tools = [
                {
                    "name": "navigate",
                    "description": "Navigate to a specific destination.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "destination": {
                                "type": "string",
                                "description": "The destination to navigate to."
                            }
                        },
                        "required": ["destination"]
                    }
                },
                {
                    "name": "current_location",
        "description": "Analyze the current location. eg: 'where are we right now?'",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
                      }
               }
            ]

            # GPT call with function calling enabled
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Specify the correct model
                messages=messages,
                functions=tools,
                function_call="auto"
            )

            return response

        except Exception as e:
            print(f"[GPT Client] Error: {e}")
            return "Sorry, I couldn't process the request."