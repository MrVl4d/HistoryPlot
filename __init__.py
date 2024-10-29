from __future__ import annotations

import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import mplcyberpunk
import datetime
import pytz
import json
import os.path
import numpy as np

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

DOMAIN = "history_plot"
_LOGGER = logging.getLogger(__name__)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    def is_float(element: any) -> bool:
        if element is None: 
            return False
        try:
            float(element)
            return True
        except ValueError:
            return False

    def create_plot(call: ServiceCall) -> None:
        # Get current timezone
        local_tz = pytz.timezone(hass.config.time_zone)

        # Read values
        entity_ids = call.data.get("entity_id", '')
        date_from = dt_util.parse_datetime(call.data.get("date_from")).replace(tzinfo=local_tz).astimezone(pytz.utc)
        date_to = call.data.get("date_to", None)
        if date_to != None :
            date_to = dt_util.parse_datetime(date_to).replace(tzinfo=local_tz).astimezone(pytz.utc)
        path_to_image = call.data.get("path_to_image", '')
        _LOGGER.info(f'Received data: entity_id: {entity_ids}, path_to_image: {path_to_image}, date_from: {date_from}, date_to: {date_to}', call.data)

        # Request history data
        history_states = get_significant_states(hass, date_from, date_to, entity_ids)

        # Filter invalid entity_ids
        filtered_entity_ids = [id for id in entity_ids if id in history_states and len(history_states[id]) > 0]

        # Validate history states
        if "unit_of_measurement" not in history_states[filtered_entity_ids[0]][0].attributes:
            raise ServiceValidationError(f"Object does not contain unit_of_measurement field({history_states[filtered_entity_ids[0]][0].attributes}).")
        history_units = list(set([history_states[id][0].attributes['unit_of_measurement'] for id in filtered_entity_ids]))
        if len(history_units) > 1:
            raise ServiceValidationError("All objects should have the same unit_of_measurement(" + ", ".join(history_units) + ").")

        # Configure Plot
        plt.style.use("cyberpunk")
        plt.figure(figsize=(8,4))
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.gca().xaxis.set_major_locator(mdates.DayLocator())
        plt.gca().xaxis.set_minor_locator(mdates.AutoDateLocator(maxticks=15))
        plt.gca().xaxis.set_minor_formatter(mdates.DateFormatter('%H:%M'))

        for entity_id in filtered_entity_ids:
            # Prepare data
            plot_x = [x.last_changed.astimezone(local_tz).replace(tzinfo=None) for x in history_states[entity_id] if is_float(x.state)]
            plot_y = [float(y.state) for y in history_states[entity_id] if is_float(y.state)]
            friendly_name = history_states[entity_id][0].attributes['friendly_name']
            _LOGGER.info(f'History entries count for \"{friendly_name}\" in given time range: {len(plot_y)}', call.data)

            if len(plot_y) < 600:
                # Plot data
                plt.plot(plot_x, plot_y, label=friendly_name)
                mplcyberpunk.add_underglow(plt.gcf().axes[-1])
            else:
                # Add plot with max/min range and average
                x_data = [x[int(len(x)/2)] for x in np.array_split(plot_x, 200)]
                y_data = [sum(y) / len(y) for y in np.array_split(plot_y, 200)]
                y_min = [min(y) for y in np.array_split(plot_y, 200)]
                y_max = [max(y) for y in np.array_split(plot_y, 200)]
                plt.plot(x_data, y_data, label=friendly_name)
                plot_color = plt.gca().lines[-1].get_color()
                plt.fill_between(x_data, y_min, y_max, alpha=0.1, color=plot_color)
        
        # Finish Plot configuration
        plt.ylabel(history_units[0])
        plt.legend()

        # Save to file
        plt.savefig(path_to_image, format=os.path.splitext(path_to_image)[1][1:])

    # Register our service with Home Assistant.
    hass.services.register(DOMAIN, 'create_plot', create_plot)

    # Return boolean to indicate that initialization was successfully.
    return True
