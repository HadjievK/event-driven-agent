#!/usr/bin/env node
/**
 * send_mail.js
 * ─────────────
 * Uses nodemailer to send emails from Gmail to Outlook recipients.
 * Reads recipients and template from markdown files.
 */

const nodemailer = require('nodemailer');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

async function sendTeamMail(eventName = 'send-team-mail', customSubject = null) {
  try {
    // Determine the event folder path
    const eventFolder = path.join(__dirname, '../../', eventName);
    
    // 1. Read recipients from team-members.md
    const recipientsPath = path.join(eventFolder, 'references/team-members.md');
    const recipientsContent = fs.readFileSync(recipientsPath, 'utf-8');
    const recipients = recipientsContent
      .split('\n')
      .map(line => line.trim())
      .filter(line => line && !line.startsWith('#'))
      .join(',');

    if (!recipients) {
      throw new Error('No recipients found in team-members.md');
    }

    // 2. Read email template from mail-template.md
    const templatePath = path.join(eventFolder, 'references/mail-template.md');
    const emailBody = fs.readFileSync(templatePath, 'utf-8');

    // 3. Configure nodemailer with Outlook/Office 365
    const transporter = nodemailer.createTransport({
      host: 'smtp.office365.com',
      port: 587,
      secure: false, // use STARTTLS
      auth: {
        user: process.env.EMAIL_USER || process.env.GMAIL_USER,  // Support both variable names
        pass: process.env.EMAIL_PASSWORD || process.env.GMAIL_APP_PASSWORD
      },
      tls: {
        ciphers: 'SSLv3'
      }
    });

    // 4. Send the email
    const mailOptions = {
      from: process.env.EMAIL_USER || process.env.GMAIL_USER,
      to: recipients,
      subject: customSubject || 'Dev Team — Status Update',
      text: emailBody
    };

    const info = await transporter.sendMail(mailOptions);
    
    const result = {
      status: 'sent',
      message_id: info.messageId,
      timestamp: new Date().toISOString(),
      recipients: recipients.split(',').length
    };

    console.log(JSON.stringify(result, null, 2));
    return result;

  } catch (error) {
    const result = {
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString()
    };
    console.error(JSON.stringify(result, null, 2));
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  const eventName = process.argv[2] || 'send-team-mail';
  const subject = process.argv[3] || null;
  sendTeamMail(eventName, subject);
}

module.exports = { sendTeamMail };
