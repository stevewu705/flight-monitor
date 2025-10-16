import requests
import json
import time
from datetime import datetime, timezone
import os

# Configuration - using environment variables for security
SEATS_API_KEY = os.environ.get("SEATS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# File to persist hourly message timestamp
HOURLY_TIMESTAMP_FILE = "/tmp/last_hourly_message.txt"
STARTUP_LOCK_FILE = "/tmp/startup_message_sent.txt"

def get_current_time():
    """Get current UTC time for consistent timezone handling"""
    return datetime.now(timezone.utc)

def should_send_startup_message():
    """Check if we should send startup message (only once per deployment)"""
    import fcntl

    try:
        # Try to acquire exclusive lock
        with open(STARTUP_LOCK_FILE, 'w') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Check if startup message was already sent for this deployment
            if os.path.exists(STARTUP_LOCK_FILE + ".sent"):
                return False

            # Mark startup message as sent
            with open(STARTUP_LOCK_FILE + ".sent", 'w') as sent_file:
                sent_file.write(get_current_time().isoformat())

            return True

    except IOError:
        # Another process already has the lock and is handling startup
        return False
    except Exception as e:
        print(f"Error in startup message check: {e}")
        return False

def check_seats(origins, destinations, start_date, end_date, cabin="business", direct_only=False):
    """Check seats availability for multiple origins/destinations"""
    origins_str = ",".join(origins) if isinstance(origins, list) else origins
    destinations_str = ",".join(destinations) if isinstance(destinations, list) else destinations

    only_direct = "true" if direct_only else "false"
    url = f"https://seats.aero/partnerapi/search?origin_airport={origins_str}&destination_airport={destinations_str}&start_date={start_date}&end_date={end_date}&take=500&include_trips=false&only_direct_flights={only_direct}&include_filtered=false&cabins={cabin}"

    headers = {
        "accept": "application/json",
        "Partner-Authorization": SEATS_API_KEY
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error checking seats: {e}")
        return None

def send_telegram_message(message):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        print("✅ Telegram message sent successfully")
        return True
    except Exception as e:
        print(f"❌ Error sending Telegram message: {e}")
        return False

def filter_by_airline(item, required_airlines):
    """Check if flight has required airlines"""
    if not required_airlines:
        return True  # No airline restriction

    airlines = item.get("JAirlines", "")  # Business class airlines
    return any(airline in airlines for airline in required_airlines)

def filter_by_direct(item, direct_only=False):
    """Check if flight is direct when required"""
    if not direct_only:
        return True
    return item.get("JDirect", False)

def filter_by_route_preferences(item, route_preferences):
    """Check if flight matches any of the route preferences"""
    if not route_preferences:
        return True  # No preferences means accept all

    origin = item.get("Route", {}).get("OriginAirport", "")
    destination = item.get("Route", {}).get("DestinationAirport", "")
    airlines = item.get("JAirlines", "")

    # Check if this flight matches any route preference
    for pref in route_preferences:
        # Check origin match
        if origin not in pref["origins"]:
            continue

        # Check destination match
        if destination not in pref["destinations"]:
            continue

        # Check airline requirement (if specified)
        if pref["airlines"]:
            if not any(airline in airlines for airline in pref["airlines"]):
                continue

        # All criteria match for this preference
        return True

    return False

def search_routes():
    """Search all defined routes for target periods"""

    # Define search configurations for your target periods (Optimized for fewer API calls)
    searches = {
        # December 5-15, 2025 (US to Asia)
        "dec_us_to_asia": {
            "date_range": ("2025-12-05", "2025-12-15"),
            "routes": {
                "alaska": [
                    {
                        "name": "ORD→HKG (Any airline, connecting OK)",
                        "origins": ["ORD"],
                        "destinations": ["HKG"],
                        "airlines": None,  # Any airline
                        "max_miles": 85000
                    },
                    {
                        "name": "US→Asia (Direct flights only)",
                        "origins": ["ORD", "DFW", "LAX", "SFO"],
                        "destinations": ["HND", "NRT", "TPE"],
                        "airlines": None,  # No airline filter - will filter in results
                        "max_miles": 75000,
                        "direct_only": True,
                        # Store original route preferences for filtering
                        "route_preferences": [
                            {"origins": ["ORD", "DFW"], "destinations": ["HND", "NRT"], "airlines": ["AA"]},
                            {"origins": ["LAX", "SFO"], "destinations": ["TPE"], "airlines": ["JX"]}
                        ]
                    }
                ],
                "aeroplan": [
                    {
                        "name": "ORD/LAX/SFO/SEA→TPE/HND/NRT (Direct only)",
                        "origins": ["ORD", "LAX", "SFO", "SEA"],
                        "destinations": ["TPE", "HND", "NRT"],
                        "airlines": None,
                        "max_miles": 87500,
                        "direct_only": True
                    }
                ]
            }
        }
    }

    all_results = []

    for period_name, period_config in searches.items():
        start_date, end_date = period_config["date_range"]

        for program, routes in period_config["routes"].items():
            for route_config in routes:
                print(f"Searching {route_config['name']} for {program}...")

                # Get flight data
                data = check_seats(
                    route_config["origins"],
                    route_config["destinations"],
                    start_date,
                    end_date,
                    direct_only=route_config.get("direct_only", False)
                )

                if not data or not data.get("data"):
                    continue

                # Filter results
                for item in data["data"]:
                    source = item.get("Route", {}).get("Source", "").lower()

                    # Check program match
                    if source != program:
                        continue

                    # Check if business class available
                    if not item.get("JAvailable") or item.get("JRemainingSeats", 0) <= 0:
                        continue

                    # Check miles limit
                    miles = int(item.get("JMileageCost", 0) or 0)
                    if miles > route_config["max_miles"]:
                        continue

                    # Check route preferences (for merged Alaska routes)
                    if route_config.get("route_preferences"):
                        if not filter_by_route_preferences(item, route_config["route_preferences"]):
                            continue
                    else:
                        # Check airline requirements (for non-merged routes like Aeroplan)
                        if not filter_by_airline(item, route_config.get("airlines")):
                            continue

                    # Check direct flight requirement
                    if not filter_by_direct(item, route_config.get("direct_only", False)):
                        continue

                    # Add to results
                    result = {
                        "period": period_name,
                        "program": program,
                        "route_name": route_config["name"],
                        "origin": item.get("Route", {}).get("OriginAirport", ""),
                        "destination": item.get("Route", {}).get("DestinationAirport", ""),
                        "date": item.get("Date", ""),
                        "miles": miles,
                        "seats": item.get("JRemainingSeats", 0),
                        "airlines": item.get("JAirlines", ""),
                        "is_direct": item.get("JDirect", False)
                    }
                    all_results.append(result)

    return all_results

def create_found_message(results):
    """Create message when flights are found"""
    if not results:
        return None

    # Group by period and program
    by_period = {}
    for result in results:
        period = result["period"]
        program = result["program"]

        if period not in by_period:
            by_period[period] = {}
        if program not in by_period[period]:
            by_period[period][program] = []

        by_period[period][program].append(result)

    # Sort results within each group
    for period in by_period:
        for program in by_period[period]:
            by_period[period][program].sort(key=lambda x: (x["date"], x["miles"]))

    # Create message
    current_time = get_current_time()
    message = f"🚨 *FLIGHTS FOUND!* 🚨\n📅 {current_time.strftime('%Y-%m-%d %H:%M UTC')}\n\n"

    for period, programs in by_period.items():
        period_title = "🎄 Dec 5-15: US→Asia"
        message += f"{period_title}\n"

        for program, flights in programs.items():
            program_emoji = "🇺🇸" if program == "alaska" else "🇨🇦"
            message += f"\n{program_emoji} *{program.upper()}*: {len(flights)} found\n"

            # Group by route name
            by_route = {}
            for flight in flights:
                route = flight["route_name"]
                if route not in by_route:
                    by_route[route] = []
                by_route[route].append(flight)

            for route_name, route_flights in by_route.items():
                message += f"  📍 *{route_name}*:\n"
                for flight in route_flights[:5]:  # Limit to 5 per route for readability
                    direct_indicator = "✈️" if flight["is_direct"] else "🔄"
                    message += f"    {direct_indicator} `{flight['origin']}→{flight['destination']}` {flight['date']}\n"
                    message += f"       💺 {flight['miles']:,d} miles ({flight['seats']} seats) [{flight['airlines']}]\n\n"

                if len(route_flights) > 5:
                    message += f"    ... and {len(route_flights) - 5} more flights\n\n"

        message += "\n"

    return message

def get_last_hourly_message():
    """Read last hourly message timestamp from file"""
    try:
        if os.path.exists(HOURLY_TIMESTAMP_FILE):
            with open(HOURLY_TIMESTAMP_FILE, 'r') as f:
                timestamp_str = f.read().strip()
                # Parse as UTC and ensure timezone awareness
                dt = datetime.fromisoformat(timestamp_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
    except Exception as e:
        print(f"Error reading hourly timestamp: {e}")
    return None

def save_last_hourly_message(timestamp):
    """Save last hourly message timestamp to file"""
    try:
        with open(HOURLY_TIMESTAMP_FILE, 'w') as f:
            f.write(timestamp.isoformat())
    except Exception as e:
        print(f"Error saving hourly timestamp: {e}")

def should_send_hourly_message():
    """Check if we should send daily 'no flights' message with file locking"""
    import fcntl

    now = get_current_time()
    current_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Use file locking to prevent race conditions between multiple instances
    lock_file_path = "/tmp/hourly_message_lock.txt"

    try:
        # Try to acquire exclusive lock
        with open(lock_file_path, 'w') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # We have the lock, now check if we should send message
            last_hourly_message = get_last_hourly_message()

            # Send message once per day (24 hours)
            if last_hourly_message is None or last_hourly_message < current_day:
                save_last_hourly_message(current_day)
                return True

            return False

    except IOError:
        # Another instance already has the lock and is handling the daily message
        return False
    except Exception as e:
        print(f"Error in daily message check: {e}")
        return False

def create_no_flights_message():
    """Create daily 'no flights found' message"""
    current_time = get_current_time()
    return f"📊 *Daily Update*\n📅 {current_time.strftime('%Y-%m-%d %H:%M UTC')}\n\n❌ No flights found matching criteria\n\n🔍 Monitoring:\n🎄 Dec 5-15, 2025: US→Asia\n\n⏰ Next check in 5 minutes..."

def check_flights_once():
    """Check flights once - called by cron every 5 minutes"""
    try:
        current_time = get_current_time()
        print(f"🔍 Checking flights at {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Search for flights
        results = search_routes()

        if results:
            # Flights found - send immediate notification
            message = create_found_message(results)
            if message:
                print(f"🚨 FOUND {len(results)} FLIGHTS - sending notification!")
                send_telegram_message(message)
        else:
            # No flights found - check if we should send daily update
            if should_send_hourly_message():
                print("📬 Sending daily 'no flights' update")
                send_telegram_message(create_no_flights_message())
            else:
                print("❌ No flights found - waiting for next check")

        return {"status": "success", "flights_found": len(results) if results else 0}

    except Exception as e:
        print(f"❌ Error in flight check: {e}")
        send_telegram_message(f"⚠️ *Monitor Error*\n\nError: {str(e)}\n\nWill retry in 5 minutes...")
        return {"status": "error", "error": str(e)}

def main():
    """Main function - for local testing"""
    print("🚀 Running single flight check...")
    result = check_flights_once()
    print(f"✅ Check completed: {result}")

if __name__ == "__main__":
    main()