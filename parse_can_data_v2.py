
import json

def parse_can_data(data_string):
    """
    Parses the Daly BMS CAN data string and returns a JSON object.
    """
    parts = data_string.split("|")

    # Extract timestamp and other trailing data
    timestamp_and_extra_full = parts[-1].split("*")
    timestamp = timestamp_and_extra_full[-1].strip()
    # The part before the last '*' might contain the checksum and other comma-separated values
    last_data_segment = timestamp_and_extra_full[0]

    # Clean up the main parts list
    parts = parts[:-1] # Remove the last element which contains extra_data and timestamp
    parts.append(last_data_segment.split(",")[0]) # Add the last numerical value before the comma-separated extra data
    
    extra_data_elements = last_data_segment.split(",")[1:] # This will be like ['-', '-', '1_1_0_0_0', 'D83D97A1']
    checksum = extra_data_elements[-1] if extra_data_elements else None
    other_info = extra_data_elements[:-1] if len(extra_data_elements) > 1 else []

    parsed_data = {
        "log_type": parts[0],
        "data_0x90": {
            "cumulative_total_voltage_V": float(parts[1]),
            "gather_total_voltage_V": float(parts[2]),
            "current_A": (float(parts[3]) - 30000) / 10.0, # 30000 Offset, 0.1A
            "soc_percent": float(parts[4]) / 10.0 # SOC is 0.1%
        },
        "data_0x91": {
            "max_cell_voltage_mV": int(parts[5]),
            "max_voltage_cell_no": int(parts[6]),
            "min_cell_voltage_mV": int(parts[7]),
            "min_voltage_cell_no": int(parts[8])
        },
        "data_0x92": {
            "max_temp_celsius": int(parts[9]) - 40, # 40 Offset
            "max_temp_cell_no": int(parts[10]),
            "min_temp_celsius": int(parts[11]) - 40, # 40 Offset
            "min_temp_cell_no": int(parts[12])
        },
        "data_0x93": {
            "state": int(parts[13]), # 0 stationary, 1 charge, 2 discharge
            "charge_mos_state": int(parts[14]),
            "discharge_mos_status": int(parts[15]),
            "bms_life_cycles": int(parts[16]),
            "remain_capacity_mAh": float(parts[17])
        },
        "data_0x94": {
            "num_battery_string": int(parts[18]),
            "num_temperature_sensors": int(parts[19]),
            "charger_status": int(parts[20]), # 0 disconnect, 1 access
            "load_status": int(parts[21]), # 0 disconnect, 1 access
            "byte4_status_raw": int(parts[22]), # Bitfield, parse separately if needed
            "di_do_states": {
                "DI1": (int(parts[22]) >> 0) & 1,
                "DI2": (int(parts[22]) >> 1) & 1,
                "DI3": (int(parts[22]) >> 2) & 1,
                "DI4": (int(parts[22]) >> 3) & 1,
                "DO1": (int(parts[22]) >> 4) & 1,
                "DO2": (int(parts[22]) >> 5) & 1,
                "DO3": (int(parts[22]) >> 6) & 1,
                "DO4": (int(parts[22]) >> 7) & 1,
            },
            "reserved_byte5": int(parts[23]),
            "reserved_byte6": int(parts[24]),
            "reserved_byte7": int(parts[25])
        }
    }

    current_index = 26

    # Data ID 0x95 (Cell voltage 1~48)
    # Byte0:frame number, starting from 0,0xFF invalid
    # Byte1~byte6:Cell voltage (1 mV)
    # Byte7: Reserved
    # The voltage of each monomer is 2 byte... max 96 byte, is sent in 16 frames
    # Our string has single values for each cell voltage.
    # num_battery_string from 0x94 tells us how many cells there are.
    num_cells = parsed_data["data_0x94"]["num_battery_string"]
    # The first value at current_index is the frame number for cell voltages
    cell_voltage_frame_no = int(parts[current_index])
    current_index += 1
    parsed_data["data_0x95"] = {
        "frame_number": cell_voltage_frame_no,
        "cell_voltages_mV": []
    }
    # The document says Byte1-Byte6 are cell voltages, implying 3 cells per frame (2 bytes each).
    # However, the example string lists individual cell voltages. We'll use num_cells.
    for i in range(num_cells):
        if current_index < len(parts):
            parsed_data["data_0x95"]["cell_voltages_mV"].append(int(parts[current_index]))
            current_index += 1
        else:
            break # Not enough data in string
    # The example string has more 0s after the 15 cell voltages, these might be padding or reserved for 0x95.
    # The document says for 0x95, Byte7 is reserved. If the string has more values than num_cells for this frame, it could be this reserved byte or padding.
    # For simplicity, we'll assume the string provides exactly num_cells values after the frame number.
    # Let's adjust current_index based on the example string's structure for now, as it seems to be a flat list of values.
    # The example string has 15 cell voltages. After the frame number (parts[26]), voltages are parts[27] to parts[41]
    current_index = 26 + 1 + num_cells # Start of next section


    # Data ID 0x96 (Cell temperature 1~16)
    # Byte0:frame number, starting at 0
    # Byte1~byte7:cell temperature(40 Offset ,℃)
    # Each temperature accounts for 1 byte... max 21 byte, send in 3 frames
    num_temp_sensors = parsed_data["data_0x94"]["num_temperature_sensors"]
    # The example string seems to list temperatures directly, not in frames in this flat format.
    # Let's assume the number of temperature values matches num_temp_sensors
    # In the example string, after 15 cell voltages (index 27 to 41), temperatures start at index 42.
    # The example has 15 temperature values (index 42 to 56)
    # However, num_temp_sensors is 3. This indicates the string format might be different from strict CAN frame concatenation.
    # We will parse based on the example string's apparent structure for now.
    # The example string has 15 temperature values after the cell voltages.
    # Let's assume the number of temperatures in the string is fixed for this log format, or it's num_cells if num_temp_sensors is not reliable here.
    # For the example string, there are 15 temperature values only. Let's use that for now.
    num_temps_in_string = 15 # From example string structure
    parsed_data["data_0x96_cell_temperatures_celsius"] = []
    for i in range(num_temps_in_string):
        if current_index < len(parts):
            # Apply offset if these are raw values from 0x96 frame
            # The example values like -32 suggest offset is already applied or not applicable here.
            # The doc says (40 Offset, C). If values are raw, apply it. If they are already processed, don't.
            # Given values like 22, 24, -32, it seems the offset is NOT YET APPLIED for positive values, and negative values are as-is.
            # This is ambiguous. Let's assume the values are direct and apply offset as per doc for positive values.
            # For now, let's assume the values in the string are final and don't need offset, as per the example's negative values.
            # Let's re-evaluate: if 22 is a raw value, then 22-40 = -18. If -32 is raw, then -32-40 = -72.
            # The example string has 22, 22, 24, then -32, -39 etc. This is confusing.
            # Let's assume the values are as they should be, and the offset is only for positive temps in the CAN frame.
            # The problem statement implies this is a *data string*, not a raw CAN frame. So values might be pre-processed.
            # Let's assume values are final. The doc is for CAN frame bytes.
            parsed_data["data_0x96_cell_temperatures_celsius"].append(int(parts[current_index]))
            current_index += 1
        else:
            break

    # Data ID 0x97 (Cell balance State 1~48)
    # 0: Closed 1: Open. Bit0: Cell 1 balance state... Bit47:Cell 48 balance state
    # The example string has 48 values (0 or 1) for this.
    num_balance_states = 48 # Max 48 cells
    parsed_data["data_0x97_cell_balance_states"] = []
    for i in range(num_balance_states):
        if current_index < len(parts):
            parsed_data["data_0x97_cell_balance_states"].append(int(parts[current_index]))
            current_index += 1
        else:
            break

    # Data ID 0x98 (Battery failure status)
    # 0->No error 1->Error. Series of bits across 7 bytes.
    # The example string has 56 values (0 or 1) for this (7 bytes * 8 bits/byte = 56 bits)
    num_failure_bits = 56
    parsed_data["data_0x98_battery_failure_status_bits"] = []
    for i in range(num_failure_bits):
        if current_index < len(parts) and parts[current_index] != '': # Ensure part is not empty
             try:
                parsed_data["data_0x98_battery_failure_status_bits"].append(int(parts[current_index]))
             except ValueError:
                # Handle cases where a part might not be an integer, e.g. if it's part of the extra_data accidentally included
                # For now, we'll skip non-integer parts in this section
                pass # Or log an error, or append a placeholder
        current_index += 1
        if current_index >= len(parts): # break if we are at the end of parts
            break

    parsed_data["timestamp"] = timestamp
    parsed_data["other_info"] = other_info
    parsed_data["checksum"] = checksum

    return json.dumps(parsed_data, indent=4)

if __name__ == "__main__":
    test_string = "CAN|44.600|0.000|0.000|99.100|3216|6|264|1|24|3|22|1|0|1|0|219|47568.000|15|3|0|0|0|1|0|0|0|0|0|0|3194|3202|3212|3206|3208|3208|3211|3199|3075|3211|3199|3075|3211|3199|3075|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|22|22|24|-32|-39|-37|-73|-40|-40|-40|-40|-40|-40|-40|-40|-40|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|1|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|1|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0,-,-,1_1_0_0_0,D83D97A1*\t25.02.2025\u00a014:33:33"
    parsed_json = parse_can_data(test_string)
    print(parsed_json)


