// Adaptateur email volontairement neutre pour le pilote.
// En production, remplacer cette implementation par un provider SMTP
// Infomaniak Mail, SendGrid, Mailgun ou un service interne.
export async function sendEmail({ to, subject, text }) {
  console.log("[email:log-adapter]", {
    to,
    subject,
    text
  });
}

