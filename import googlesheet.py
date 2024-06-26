import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import asyncio

# Telegram Bot Token
TOKEN = '6332330468:AAFz9Mj3Bl1d2ANf9ug4IuB2PcsTvH2yYUE'

# Google Sheets credentials
SPREADSHEET_ID = '12BC9uSjoTNg2Yg4HfWxKj5PJPpHcah5iAFYFdW_XcRU'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Initialize Google Sheets client
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name('C:/Users/Anuj/AppData/Local/Programs/Python/credentials.json', SCOPES)  # Replace with the path to your credentials
    client = gspread.authorize(creds)
    print("Google Sheets client initialized successfully.")
except Exception as e:
    print(f"Error initializing Google Sheets client: {e}")

# Define states
ASK_REASON, ASK_INVOICE, ASK_AMOUNT, ASK_RECEIVED, ASK_STATUS_UPDATE, ASK_UPDATE_STATUS = range(6)

# Start command handler
async def start(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome to Expense Tracker Bot! Send /expense to log your expenses or /status to update the status of an expense.")

# Conversation handler entry point for logging expenses
async def start_expense(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide the reason for the expense.")
    return ASK_REASON

# Ask reason handler
async def ask_reason(update, context):
    context.user_data['reason'] = update.message.text
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide the invoice details (Google Drive link or PDF).")
    return ASK_INVOICE

# Ask invoice handler
async def ask_invoice(update, context):
    if update.message.document:
        context.user_data['invoice'] = update.message.document.file_id
    elif update.message.photo:
        context.user_data['invoice'] = update.message.photo[-1].file_id
    elif update.message.text:
        if update.message.text.startswith("http://") or update.message.text.startswith("https://"):
            context.user_data['invoice'] = update.message.text
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide drive link or pdf.")
            return ASK_INVOICE
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide drive link or pdf.")
        return ASK_INVOICE

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide the expense amount in ₹ (Rupees).")
    return ASK_AMOUNT


# Ask amount handler
async def ask_amount(update, context):
    try:
        amount_text = update.message.text
        amount = float(amount_text)
        context.user_data['amount'] = amount
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text="How much money was received (if any)? If none, type 0 or 'Pending' if it's not received yet.")
        return ASK_RECEIVED
    except ValueError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid amount. Please provide a valid number for the expense amount in ₹ (Rupees).")
        return ASK_AMOUNT

# Ask received amount or status handler
async def ask_received_or_status(update, context):
    received_text = update.message.text.strip().lower()
    if received_text.isdigit():
        received = float(received_text)
        context.user_data['received'] = received
        status = "Received" if received > 0 else "Pending"
    elif received_text == "pending":
        context.user_data['received'] = 0
        status = "Pending"
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid input. Please type either a number for received amount or 'Pending'.")
        return ASK_RECEIVED

    username = update.message.from_user.username
    user_sheet = get_or_create_user_sheet(username)
    reason = context.user_data['reason']
    invoice = context.user_data['invoice']
    amount = context.user_data['amount']
    received = context.user_data['received']

    row = [f"₹{amount}", reason, invoice, f"₹{received}", status]
    user_sheet.append_row(row)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Expense logged: ₹{amount} for {reason} with invoice {invoice}. Status: {status}")
    return ConversationHandler.END


# Function to get user's sheet or create new if not exists
def get_or_create_user_sheet(username):
    try:
        if not client or not SPREADSHEET_ID:
            raise ValueError("Client and SPREADSHEET_ID must be initialized")

        # Set a default name if the username is None
        sheet_name = f"{username if username else 'Guest'}'s Expenses"
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        user_sheets = spreadsheet.worksheets()

        for sheet in user_sheets:
            if sheet.title == sheet_name:
                return sheet

        new_sheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="20")
        headers = ['Exped. Amount', 'Reason', 'Invoice', 'Received Amount', 'Status']

        if new_sheet:
            new_sheet.append_row(headers)
            return new_sheet
        else:
            raise Exception("Failed to create a new sheet")

    except gspread.SpreadsheetNotFound:
        print("Spreadsheet not found. Please check the SPREADSHEET_ID.")
    except gspread.APIError as api_error:
        print(f"API error occurred: {api_error}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")





# Status update entry point
async def start_status_update(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide the invoice details to update the status.")
    return ASK_STATUS_UPDATE

# Status update handler
async def ask_status_update(update, context):
    try:
        invoice = update.message.text
        username = update.message.from_user.username
        user_sheet = get_or_create_user_sheet(username)
        cell = user_sheet.find(invoice)
        
        if cell:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Do you want to update the status of invoice {invoice} to 'Received'? Reply 'Yes' or 'No'.")
            context.user_data['cell'] = cell
            return ASK_UPDATE_STATUS
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Invoice {invoice} not found.")
            return ConversationHandler.END
    except Exception as e:
        print(f"Error updating status: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to update status. Please try again.")
        return ConversationHandler.END


# Ask update status handler
async def ask_update_status(update, context):
    response = update.message.text.strip().lower()
    if response == 'yes':
        user_sheet = get_or_create_user_sheet(update.message.from_user.username)
        cell = context.user_data['cell']
        user_sheet.update_cell(cell.row, 6, "Received")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Status updated for invoice {cell.value} to 'Received'.")
    elif response == 'no':
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Status update cancelled.")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid response. Please reply with 'Yes' or 'No'.")

    return ConversationHandler.END

# Cancel handler
async def cancel(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Operation cancelled.")
    return ConversationHandler.END



# Display summary handler with improved error handling and debugging
async def display_summary(update, context):
    try:
        username = update.message.from_user.username
        user_sheet = get_or_create_user_sheet(username)

        expected_headers = ['Expend. Amount', 'Reason', 'Invoice', 'Received Amount', 'Status']
        
        expenses = user_sheet.get_all_records(expected_headers=expected_headers)

        def parse_currency(value):
            try:
                return float(value.replace('₹', '').replace(',', '').strip())
            except ValueError:
                return 0.0

        total_spent = sum(parse_currency(expense.get('Expend. Amount', '₹0')) for expense in expenses)
        total_received = sum(parse_currency(expense.get('Received Amount', '₹0')) for expense in expenses if expense.get('Status') == 'Received')
        total_pending = sum(parse_currency(expense.get('Expend. Amount', '₹0')) - parse_currency(expense.get('Received', '₹0')) for expense in expenses if expense.get('Status') == 'Pending')

        summary_text = (f"Total spent: ₹{total_spent}\n"
                        f"Total received: ₹{total_received}\n"
                        f"Total pending: ₹{total_pending}")

        await context.bot.send_message(chat_id=update.effective_chat.id, text=summary_text)
    except Exception as e:
        print(f"Error displaying summary: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Failed to display summary. Error: {e}")


def main():
    app = Application.builder().token(TOKEN).build()

    # Conversation handler for logging expenses
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('expense', start_expense)],
        states={
            ASK_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_reason)],
            ASK_INVOICE: [MessageHandler(filters.TEXT | filters.Document.ALL | filters.PHOTO & ~filters.COMMAND, ask_invoice)],
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
            ASK_RECEIVED: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_received_or_status)],
            ASK_UPDATE_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_update_status)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Conversation handler for updating status
    status_update_handler = ConversationHandler(
        entry_points=[CommandHandler('status', start_status_update)],
        states={
            ASK_STATUS_UPDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_status_update)],
            ASK_UPDATE_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_update_status)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Command handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('summary', display_summary))
    app.add_handler(conv_handler)
    app.add_handler(status_update_handler)

    app.run_polling()

if __name__ == '__main__':
    main()


# Done