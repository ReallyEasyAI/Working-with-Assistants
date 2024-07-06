import requests
import json
from typing_extensions import override
from openai import AssistantEventHandler, OpenAI

# Create an OpenAI client instance
client = OpenAI()

import requests

def get_lat_lon(city_name, state_name=None):
    """
    Get the latitude and longitude for a given city (and state).
    Uses the geocode.xyz API to get the coordinates.
    Parameters:
        city_name (str): The name of the city
        state_name (str, optional): The name of the state (if applicable)
    Returns:
        tuple: Latitude and longitude as floats, or (None, None) if not found
    """
    if state_name:
        location = f"{city_name},{state_name}"
    else:
        location = city_name
    
    # URL for the geocode API
    geocode_url = f"https://geocode.xyz/{location}?json=1"
    response = requests.get(geocode_url)
    
    if response.status_code == 200:
        data = response.json()
        if 'latt' in data and 'longt' in data:
            # Return the latitude and longitude
            return float(data['latt']), float(data['longt'])
        else:
            # Error handling if coordinates are not found
            print("Error: Could not find latitude and longitude for the location.")
            return None, None
    else:
        # Error handling for failed request
        print("Error: Geocoding request failed.")
        return None, None

def get_weather_forecast(lat, lon):
    """
    Get the weather forecast for a given latitude and longitude.
    Uses the weather.gov API to get the forecast.
    Parameters:
        lat (float): Latitude
        lon (float): Longitude
    Returns:
        int: Temperature in Fahrenheit, or None if failed
    """
    # URL to get weather points based on coordinates
    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    response = requests.get(points_url, headers={'User-Agent': 'MyWeatherApp (contact@example.com)'})
    
    if response.status_code == 200:
        data = response.json()
        forecast_hourly_url = data['properties']['forecastHourly']
        
        # Fetch the hourly forecast data
        forecast_response = requests.get(forecast_hourly_url, headers={'User-Agent': 'MyWeatherApp (contact@example.com)'})
        if forecast_response.status_code == 200:
            forecast_data = forecast_response.json()
            # Return the temperature from the first forecast period
            return forecast_data['properties']['periods'][0]['temperature']
        else:
            # Error handling for failed forecast request
            print("Error: Hourly forecast request failed.")
            return None
    else:
        # Error handling for failed points request
        print("Error: Points request failed.")
        return None

def get_temperature(city_name, state_name=None):
    """
    Get the temperature for a given city (and state).
    First gets the coordinates, then fetches the weather forecast.
    Parameters:
        city_name (str): The name of the city
        state_name (str, optional): The name of the state (if applicable)
    Returns:
        int: Temperature in Fahrenheit, or None if failed
    """
    # Get latitude and longitude for the city
    lat, lon = get_lat_lon(city_name, state_name)
    if lat is not None and lon is not None:
        # Get the weather forecast based on coordinates
        temperature = get_weather_forecast(lat, lon)
        return temperature
    else:
        return None


class EventHandler(AssistantEventHandler):
	"""
	Custom event handler for handling actions required by the assistant.
	"""
	@override
	def on_event(self, event):
		"""
		Event handler for assistant events.
		Parameters:
			event (Event): The event to handle
		"""
		if event.event == 'thread.run.requires_action':
			run_id = event.data.id
			self.handle_requires_action(event.data, run_id)

	def handle_requires_action(self, data, run_id):
		"""
		Handles actions required by the assistant, specifically calling the get_temperature function.
		Parameters:
			data (dict): The data associated with the required action
			run_id (str): The ID of the current run
		"""
		tool_outputs = []
		
		for tool in data.required_action.submit_tool_outputs.tool_calls:
			if tool.function.name == "get_temperature":
				# Parse the arguments for the function call
				arguments = json.loads(tool.function.arguments)
				location = arguments['location']
				city_state = location.split(", ")
				city = city_state[0]
				state = city_state[1] if len(city_state) > 1 else None
				# Call the get_temperature function and prepare the output
				temperature = get_temperature(city, state)
				tool_outputs.append({"tool_call_id": tool.id, "output": str(temperature)})
		
		self.submit_tool_outputs(tool_outputs, run_id)

	def submit_tool_outputs(self, tool_outputs, run_id):
		"""
		Submits the outputs of the tools called by the assistant.
		Parameters:
			tool_outputs (list): List of tool outputs to submit
			run_id (str): The ID of the current run
		"""
		with client.beta.threads.runs.submit_tool_outputs_stream(
			thread_id=self.current_run.thread_id,
			run_id=self.current_run.id,
			tool_outputs=tool_outputs,
			event_handler=EventHandler(),
		) as stream:
			for text in stream.text_deltas:
				print(text, end="", flush=True)
			print()

# Define the assistant with instructions and available tools
assistant = client.beta.assistants.create(
	instructions="You are a weather bot. Use the provided functions to answer questions.",
	model="gpt-4o",
	tools=[
		{
			"type": "function",
			"function": {
				"name": "get_temperature",
				"description": "Get the current temperature for a specific location",
				"parameters": {
					"type": "object",
					"properties": {
						"location": {
							"type": "string",
							"description": "The city and state, e.g., San Francisco, CA"
						}
					},
					"required": ["location"]
				}
			}
		}
	]
)

# Create a new thread for the conversation
thread = client.beta.threads.create()

# Add a user message to the thread
message = client.beta.threads.messages.create(
	thread_id=thread.id,
	role="user",
	content="What's the temperature in Houston, TX?",
)

# Stream the assistant's response to completion
with client.beta.threads.runs.stream(
	thread_id=thread.id,
	assistant_id=assistant.id,
	event_handler=EventHandler()
) as stream:
	stream.until_done()
