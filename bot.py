import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token from environment
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found in environment variables!")
    raise ValueError("BOT_TOKEN must be set in environment variables")

logger.info(f"Bot token found: {BOT_TOKEN[:10]}...")

# Store user sessions temporarily
user_sessions = {}

# Telethon API credentials storage
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    try:
        user = update.effective_user
        logger.info(f"User {user.id} ({user.first_name}) started the bot")
        
        welcome_text = f"""
👋 Welcome {user.first_name}!

🔐 **Telegram Session String Generator Bot**

This bot helps you generate a Telethon session string for your Telegram account.

⚠️ **IMPORTANT SECURITY WARNING:**
- Never share your session string with anyone
- It gives full access to your Telegram account
- Only use it in your own applications

📝 **How to use:**
1. Click /generate to start
2. Send your API_ID
3. Send your API_HASH
4. Send your phone number
5. Enter the verification code
6. Get your session string!

💡 **Get API credentials from:**
https://my.telegram.org/auth

Ready? Click /generate to begin! 🚀
"""
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        logger.info(f"Sent welcome message to user {user.id}")
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        await update.message.reply_text("An error occurred. Please try again.")

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the session generation process"""
    user_id = update.effective_user.id
    
    # Reset user data
    user_data[user_id] = {'step': 'api_id'}
    
    await update.message.reply_text(
        "🔑 **Step 1/4: API ID**\n\n"
        "Please send your API_ID (numbers only)\n\n"
        "Get it from: https://my.telegram.org/auth",
        parse_mode='Markdown'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current operation"""
    user_id = update.effective_user.id
    
    if user_id in user_data:
        del user_data[user_id]
    if user_id in user_sessions:
        try:
            await user_sessions[user_id].disconnect()
        except:
            pass
        del user_sessions[user_id]
    
    await update.message.reply_text(
        "❌ Operation cancelled.\n\n"
        "Use /generate to start again.",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages based on current step"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    if user_id not in user_data:
        await update.message.reply_text(
            "Please start with /generate command first!"
        )
        return
    
    step = user_data[user_id].get('step')
    
    try:
        if step == 'api_id':
            # Validate API ID
            api_id = int(message_text.strip())
            user_data[user_id]['api_id'] = api_id
            user_data[user_id]['step'] = 'api_hash'
            
            await update.message.reply_text(
                "✅ API ID saved!\n\n"
                "🔑 **Step 2/4: API HASH**\n\n"
                "Please send your API_HASH",
                parse_mode='Markdown'
            )
        
        elif step == 'api_hash':
            api_hash = message_text.strip()
            user_data[user_id]['api_hash'] = api_hash
            user_data[user_id]['step'] = 'phone'
            
            await update.message.reply_text(
                "✅ API HASH saved!\n\n"
                "📱 **Step 3/4: Phone Number**\n\n"
                "Send your phone number with country code\n"
                "Example: +919876543210",
                parse_mode='Markdown'
            )
        
        elif step == 'phone':
            phone = message_text.strip()
            user_data[user_id]['phone'] = phone
            
            # Create Telethon client
            api_id = user_data[user_id]['api_id']
            api_hash = user_data[user_id]['api_hash']
            
            await update.message.reply_text(
                "⏳ Connecting to Telegram...",
                parse_mode='Markdown'
            )
            
            client = TelegramClient(StringSession(), api_id, api_hash)
            await client.connect()
            
            # Send code request
            try:
                await client.send_code_request(phone)
                user_sessions[user_id] = client
                user_data[user_id]['step'] = 'code'
                
                await update.message.reply_text(
                    "✅ Code sent to your Telegram!\n\n"
                    "🔢 **Step 4/4: Verification Code**\n\n"
                    "Check your Telegram app and send the code here",
                    parse_mode='Markdown'
                )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Error: {str(e)}\n\n"
                    "Please check your phone number and try again with /generate"
                )
                await cleanup_user(user_id)
        
        elif step == 'code':
            code = message_text.strip().replace('-', '')
            phone = user_data[user_id]['phone']
            client = user_sessions[user_id]
            
            await update.message.reply_text(
                "⏳ Verifying code...",
                parse_mode='Markdown'
            )
            
            try:
                await client.sign_in(phone, code)
                
                # Generate session string
                session_string = client.session.save()
                
                await update.message.reply_text(
                    "🎉 **SUCCESS!**\n\n"
                    "✅ Your session string has been generated!\n\n"
                    "⚠️ **KEEP IT SECRET - Don't share with anyone!**",
                    parse_mode='Markdown'
                )
                
                # Send session string in a separate message
                await update.message.reply_text(
                    f"`{session_string}`",
                    parse_mode='Markdown'
                )
                
                await update.message.reply_text(
                    "📝 **How to use:**\n"
                    "1. Copy the session string above\n"
                    "2. Add it to your Render environment as SESSION_STRING\n"
                    "3. Deploy your bot!\n\n"
                    "Use /generate to create another session.",
                    parse_mode='Markdown'
                )
                
                await cleanup_user(user_id)
                
            except SessionPasswordNeededError:
                user_data[user_id]['step'] = '2fa'
                await update.message.reply_text(
                    "🔐 **2FA Password Required**\n\n"
                    "Your account has Two-Factor Authentication enabled.\n"
                    "Please send your 2FA password:",
                    parse_mode='Markdown'
                )
            except PhoneCodeInvalidError:
                await update.message.reply_text(
                    "❌ Invalid code!\n\n"
                    "Please send the correct verification code or use /cancel to restart."
                )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Error: {str(e)}\n\n"
                    "Use /cancel to restart."
                )
                await cleanup_user(user_id)
        
        elif step == '2fa':
            password = message_text.strip()
            client = user_sessions[user_id]
            
            await update.message.reply_text(
                "⏳ Verifying password...",
                parse_mode='Markdown'
            )
            
            try:
                await client.sign_in(password=password)
                
                # Generate session string
                session_string = client.session.save()
                
                await update.message.reply_text(
                    "🎉 **SUCCESS!**\n\n"
                    "✅ Your session string has been generated!\n\n"
                    "⚠️ **KEEP IT SECRET - Don't share with anyone!**",
                    parse_mode='Markdown'
                )
                
                await update.message.reply_text(
                    f"`{session_string}`",
                    parse_mode='Markdown'
                )
                
                await update.message.reply_text(
                    "📝 **How to use:**\n"
                    "1. Copy the session string above\n"
                    "2. Add it to your Render environment as SESSION_STRING\n"
                    "3. Deploy your bot!\n\n"
                    "Use /generate to create another session.",
                    parse_mode='Markdown'
                )
                
                await cleanup_user(user_id)
                
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Error: {str(e)}\n\n"
                    "Please check your password and try again with /generate"
                )
                await cleanup_user(user_id)
    
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input! Please send a valid number for API_ID."
        )
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text(
            f"❌ An error occurred: {str(e)}\n\n"
            "Use /cancel to restart."
        )

async def cleanup_user(user_id):
    """Clean up user data and sessions"""
    if user_id in user_sessions:
        try:
            await user_sessions[user_id].disconnect()
        except:
            pass
        del user_sessions[user_id]
    if user_id in user_data:
        del user_data[user_id]

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = """
🆘 **Help - Session String Generator Bot**

**Commands:**
/start - Start the bot
/generate - Generate a new session string
/cancel - Cancel current operation
/help - Show this help message

**Steps to generate:**
1. Use /generate
2. Send API_ID (from my.telegram.org)
3. Send API_HASH
4. Send phone number (+919876543210)
5. Send verification code from Telegram
6. If 2FA enabled, send password
7. Copy your session string!

**Security Tips:**
⚠️ Never share your session string
⚠️ Use only in your own apps
⚠️ Don't send it to anyone

**Need API credentials?**
Visit: https://my.telegram.org/auth
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """Start the bot"""
    try:
        logger.info("Starting Session Generator Bot...")
        logger.info(f"Using bot token: {BOT_TOKEN[:15]}...")
        
        # Create application with proper settings
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .read_timeout(30)
            .write_timeout(30)
            .connect_timeout(30)
            .pool_timeout(30)
            .build()
        )
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("generate", generate))
        application.add_handler(CommandHandler("cancel", cancel))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Start bot
        logger.info("Bot handlers registered successfully!")
        logger.info("Starting polling...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
