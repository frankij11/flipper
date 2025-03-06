"""
Notification - Send email alerts for new potential deals
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import List, Dict, Any, Optional
import os
from config import credentials

logger = logging.getLogger(__name__)

def send_email(subject: str, deals: Optional[List[Dict[str, Any]]] = None, 
               message: Optional[str] = None, attachment_path: Optional[str] = None) -> bool:
    """
    Send an email notification with deal information
    
    Args:
        subject: Email subject
        deals: List of deals to include (optional)
        message: Custom message text (optional)
        attachment_path: Path to file to attach (optional)
        
    Returns:
        Boolean indicating success
    """
    try:
        # Setup email parameters
        sender = credentials.EMAIL_SENDER
        recipient = credentials.EMAIL_RECIPIENT
        password = credentials.EMAIL_PASSWORD
        
        # Create the email
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject
        
        # Build the email body
        body = ""
        
        # Add custom message if provided
        if message:
            body += message + "\n\n"
        
        # Add deals if provided
        if deals:
            body += f"Found {len(deals)} potential flip properties:\n\n"
            
            for i, deal in enumerate(deals, 1):
                body += f"{i}. {deal['address']}\n"
                body += f"   List Price: ${deal['list_price']:,.2f}, ARV: ${deal['arv']:,.2f}\n"
                body += f"   Repair: ${deal['repair_costs']:,.2f}, Profit: ${deal['potential_profit']:,.2f}\n"
                body += f"   ROI: {deal['roi']:.2f}%, Score: {deal['score']:.2f}\n"
                body += "\n"
        
        # Add the body to the email
        msg.attach(MIMEText(body, 'plain'))
        
        # Add attachment if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as file:
                attachment = MIMEApplication(file.read(), Name=os.path.basename(attachment_path))
                attachment['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(attachment)
        
        # Connect to the SMTP server and send
        with smtplib.SMTP(credentials.SMTP_SERVER, credentials.SMTP_PORT) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        
        logger.info(f"Email notification sent to {recipient}")
        return True
    
    except Exception as e:
        logger.error(f"Error sending email notification: {str(e)}")
        return False