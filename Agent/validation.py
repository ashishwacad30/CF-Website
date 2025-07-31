
# # Geoapify
# import requests
# from geopy.distance import geodesic

# GEOAPIFY_API_KEY = "ec2edb750eda45ceac3c932cd942c80a"

# def geocode_address(address: str):
#     url = f"https://api.geoapify.com/v1/geocode/search?text={address}&apiKey={GEOAPIFY_API_KEY}"
#     response = requests.get(url)
#     response.raise_for_status()
#     data = response.json()

#     if not data["features"]:
#         raise ValueError("Could not geocode the address")

#     feature = data["features"][0]
#     props = feature["properties"]

#     print("Geoapify geocode response:", props)

#     lat = feature["geometry"]["coordinates"][1]
#     lon = feature["geometry"]["coordinates"][0]
#     postcode = props.get("postcode") or props.get("postal_code") or ""
#     postcode = postcode.upper()
#     community = (
#         props.get("city")
#         or props.get("county")
#         or props.get("state_district")
#         or props.get("region")
#         or props.get("village")
#         or props.get("municipality")
#         or props.get("name")
#         or ""
#     )

#     return {
#         "resolved_community": community.strip()
#     }

# def validate_and_trigger_agents(address: str, input_community_name: str):
#     try:
#         geo_info = geocode_address(address)
#         resolved_community_name = geo_info["resolved_community"]

#         print(f"Geo-resolved community: {resolved_community_name}")
#         print(f"Input community name: {input_community_name}")

#         if resolved_community_name.lower() == input_community_name.lower():
#             return {
#                 "status": "success",
#                 "message": f"Address matched with community '{resolved_community_name}'"
#             }
#         else:
#             return {
#                 "status": "failed",
#                 "reason": f"Address does not match the given community name. Expected '{input_community_name}', but found '{resolved_community_name}'."
#             }

#     except Exception as e:
#         return {"status": "error", "message": str(e)}



# import requests

# GEOAPIFY_API_KEY = "ec2edb750eda45ceac3c932cd942c80a"

# def geocode_address(address: str):
#     url = f"https://api.geoapify.com/v1/geocode/search?text={address}&apiKey={GEOAPIFY_API_KEY}"
#     response = requests.get(url)
#     response.raise_for_status()
#     data = response.json()

#     if not data["features"]:
#         raise ValueError("Could not geocode the address")

#     props = data["features"][0]["properties"]
#     print(props)
#     community = (
#         props.get("city")
#         or props.get("village")
#         or props.get("municipality")
#         or props.get("county")
#         or props.get("region")
#         or props.get("state_district")
#         or props.get("name")
#         or ""
#     )

#     return {
#         "resolved_community": community.strip()
#     }

# def validate_and_trigger_agents(address: str, input_community_name: str):
#     try:
#         geo_info = geocode_address(address)
#         resolved_community_name = geo_info["resolved_community"]

#         print(f"Geo-resolved community: {resolved_community_name}")
#         print(f"Input community name: {input_community_name}")

#         if resolved_community_name.lower() == input_community_name.lower():
#             return {
#                 "status": "success",
#                 "message": f"Address matched with community '{resolved_community_name}'"
#             }
#         else:
#             return {
#                 "status": "failed",
#                 "reason": f"Address does not match the given community name. Expected '{input_community_name}', but found '{resolved_community_name}'."
#             }

#     except Exception as e:
#         return {"status": "error", "message": str(e)}


import requests
from geopy.distance import geodesic

GEOAPIFY_API_KEY = "ec2edb750eda45ceac3c932cd942c80a"

def geocode_address(address: str):
    url = f"https://api.geoapify.com/v1/geocode/search?text={address}&apiKey={GEOAPIFY_API_KEY}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    if not data["features"]:
        raise ValueError("Could not geocode the address")

    feature = data["features"][0]
    props = feature["properties"]

    print("Geoapify geocode response:", props)

    lat = feature["geometry"]["coordinates"][1]
    lon = feature["geometry"]["coordinates"][0]
    postcode = props.get("postcode") or props.get("postal_code") or ""
    postcode = postcode.upper()
    community = (
        props.get("city")
        or props.get("county")
        or props.get("state_district")
        or props.get("region")
        or props.get("village")
        or props.get("municipality")
        or props.get("name")
        or ""
    )

    return {
        "resolved_community": community.strip()
    }

def validate_and_trigger_agents(address: str, input_community_name: str):
    try:
        geo_info = geocode_address(address)
        resolved_community_name = geo_info["resolved_community"]

        print(f"Geo-resolved community: {resolved_community_name}")
        print(f"Input community name: {input_community_name}")

        # Normalize both names and check for substring match in either direction
        resolved = resolved_community_name.lower()
        input_name = input_community_name.lower()

        if input_name in resolved or resolved in input_name:
            return {
                "status": "success",
                "message": f"Address matched with community '{resolved_community_name}'"
            }
        else:
            return {
                "status": "failed",
                "reason": f"Address does not match the given community name. Expected '{input_community_name}', but found '{resolved_community_name}'."
            }

    except Exception as e:
        return {"status": "error", "message": str(e)}