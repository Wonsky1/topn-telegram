# Centralized bot response texts for monitoring flows

# --- Monitoring Creation ---
SEND_URL = "Please send an OLX URL (must start with https://olx.pl/…)"
INVALID_URL = (
    "❌ URL must start with https://olx.pl/… and not include sub-domains. Try again"
)
URL_NOT_REACHABLE = "❌ This URL is not reachable. Send another"
DUPLICATE_URL = "❌ You already have monitoring for this URL. Choose another URL or stop the existing monitoring first"
SEND_NAME = "Great! Now send a name for this monitoring (max 64 characters)"
INVALID_NAME = "❌ Name must be between 1 and 64 characters. Try again"
DUPLICATE_NAME = "❌ You already have monitoring with this name. Choose another name"
MONITORING_CREATED = "✅ Monitoring *{name}* started!\n🔗 [View url]({url})"
MONITORING_CREATED_WITH_DISTRICTS = (
    "✅ Monitoring *{name}* started!\n"
    "🔗 [View url]({url})\n"
    "🏘 Filtering: {district_count} district(s) selected"
)

# --- District Selection ---
DISTRICTS_FOUND = (
    "🏘 Found *{count}* districts in *{city}*.\n\n"
    "Select districts you want to receive notifications for.\n"
    "Empty selection = all districts."
)
DISTRICTS_SELECTION_HEADER = (
    "🏘 *{city}* — Select districts (page {page}/{total_pages}):"
)
DISTRICTS_SAVED = "✅ District filter saved: {count} district(s) selected"
DISTRICTS_SKIP = "Skipping district filter — you'll receive all listings"
NO_DISTRICTS_AVAILABLE = "No districts found for this city yet. Skipping filter."

# --- Monitoring Stop ---
STOPPED = "🛑 Monitoring *{name}* stopped"
ERROR_STOP = "Error stopping monitoring. Please try again later"
RESERVED_NAME = "❌ This is a reserved command name. Please choose a valid monitoring"

# --- Status ---
NO_MONITORINGS = "📋 *No active monitoring found*"
CHOOSE_MONITORING = "Choose monitoring to view status:"
UNKNOWN_MONITORING = "Unknown monitoring name. Try again"

# --- Navigation ---
BACK_TO_MENU = "Back to main menu"
MAIN_MENU = "Main menu:"

# --- General ---
ERROR_CREATING = "Error creating monitoring. Please try again later"

# --- Item Notification ---
ITEMS_FOUND_CAPTION = "I have found {count} items for monitoring '{monitoring}', maybe one of them is what you're looking for"
