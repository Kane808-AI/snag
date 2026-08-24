# Stripe setup for TokAction — plain-English runbook

**Goal:** when someone taps **Pro** in the Telegram bot, they pay on a
Stripe-hosted checkout page, and the bot upgrades them automatically (and
downgrades them when they cancel). Nothing here needs code. You copy **4
values** into one file at the end.

Everything in the code is already wired up and waiting. This is the last mile.

---

## Before you start (5 minutes)

1. **A Stripe account** — sign up at <https://dashboard.stripe.com> (free).
   New accounts start in **test mode**, which is perfect for trying things with
   fake cards. When you're ready for real customers you flip to **live mode**
   and re-copy the keys (they are different in each mode).
2. **A public web address** where the site lives (or will live), for example
   `https://tokaction.com`. This becomes your **PUBLIC_BASE_URL**. Stripe uses
   it for the "payment done" / "payment canceled" pages and for the webhook.

---

## Step 1 — Create the subscription product and price

1. Log in at <https://dashboard.stripe.com>.
2. Left menu: **Product catalog** → **Add product**.
3. **Name:** `TokAction Pro` (this is what customers see on the checkout page).
4. **Description** (optional): `Unlimited videos, longer videos, priority processing.`
5. **Pricing model:** choose **Recurring**.
6. **Price:** `7.99` · **USD** · **per month** (the site shows $7.99/mo — keep them in sync).
7. Click **Save product**.
8. On the product page, find the price you just created. **Copy its Price ID**
   — it starts with `price_` (e.g. `price_1Qx...`). This is your
   **STRIPE_PRICE_ID**.

## Step 2 — Get your two secret keys

### Secret API key (STRIPE_SECRET_KEY)
1. Left menu: **Developers** → **API keys**.
2. Click **Reveal secret key** — it starts with `sk_` (`sk_test_...` in test
   mode, `sk_live_...` in live mode). Copy it now; Stripe only shows it once.
3. Treat it like a password. Never paste it into a chat or a website.

### Webhook signing secret (STRIPE_WEBHOOK_SECRET)
The webhook is how Stripe tells the bot "this customer paid" so the bot can
upgrade them.

1. Left menu: **Developers** → **Webhooks** → **Add endpoint**.
2. **Endpoint URL:** `https://YOUR-DOMAIN/webhook` — replace `YOUR-DOMAIN` with
   your **PUBLIC_BASE_URL** domain (e.g. `https://tokaction.com/webhook`).
3. Under **Events**, click **Select events** and pick these three:
   - `checkout.session.completed` — the important one (payment succeeded)
   - `customer.subscription.deleted`
   - `customer.subscription.paused`

   (Choosing "Listen to all events" also works fine.)
4. Click **Add endpoint**.
5. On the endpoint's page, under **Signing secret**, click **Reveal**. Copy the
   secret — it starts with `whsec_...`. This is your **STRIPE_WEBHOOK_SECRET**.

## Step 3 — Know your PUBLIC_BASE_URL

The public address of the site, **no trailing slash**:

    https://tokaction.com

Stripe sends customers to `https://tokaction.com/upgrade/success` after a
successful payment and `https://tokaction.com/upgrade/cancel` if they bail.
Those two pages already exist in the repo:
`site/upgrade-success.html` and `site/upgrade-cancel.html`.

**Hosting note:** if your host doesn't automatically map the URL
`/upgrade/success` to the file `upgrade-success.html`, add a redirect rule.
On Netlify that's a `_redirects` file in `site/` with two lines:

    /upgrade/success /upgrade-success.html 200
    /upgrade/cancel /upgrade-cancel.html 200

## Step 4 — Paste the four values into the .env file

Open `~/.hermes/workspace/snag/.env` in a text editor and add these four lines
(no quotes around the values):

    STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxxxxx
    STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxx
    STRIPE_PRICE_ID=price_xxxxxxxxxxxxxxxx
    PUBLIC_BASE_URL=https://tokaction.com

Replace the `xxx...` parts with what you copied:

| Value in .env               | Comes from                          | Starts with |
|-----------------------------|-------------------------------------|-------------|
| `STRIPE_SECRET_KEY`         | Step 2, API keys → secret key       | `sk_`       |
| `STRIPE_WEBHOOK_SECRET`     | Step 2, webhook → signing secret    | `whsec_`    |
| `STRIPE_PRICE_ID`           | Step 1, the price you created       | `price_`    |
| `PUBLIC_BASE_URL`           | Step 3, your site's public address  | `https://`  |

Save the file. Keep `.env` private — it holds passwords.

## Step 5 — Restart and test

1. **Restart** the bot, and make sure the webhook receiver is running (it must
   run 24/7 like the bot — ask your developer to add it to the same launchd
   setup under `deploy/`, e.g. `python3 webhook_server.py` from the snag folder).
2. From the Telegram bot, tap **/upgrade** — you should get a Stripe checkout link.
3. Pay with Stripe's test card **`4242 4242 4242 4242`** (any future expiry, any
   CVC) — test cards only work while your account is in **test mode**.
4. You land on the success page. Back in Telegram, you're now **Pro**.
5. Cancel test: in the Stripe dashboard, open the subscription and cancel it.
   The bot should drop that user back to **Free** (the
   `customer.subscription.deleted` event).

## Troubleshooting

- **Paid but not upgraded:** Stripe dashboard → **Developers → Webhooks** →
  your endpoint → **Recent deliveries**. A red row with 4xx/5xx means the
  server rejected it — check the bot's logs in `logs/`.
- **/upgrade says not available:** one of the four `.env` values is missing or
  mistyped. From the snag folder run `python3 webhook_server.py --check` — it
  lists which keys are missing (it never prints the values themselves).
- **Webhook says "bad signature":** the `STRIPE_WEBHOOK_SECRET` doesn't match
  the endpoint's signing secret, or you pasted an extra space/newline. Re-copy
  the `whsec_...` value.
- **Checkout page shows the wrong price:** update the product/price in Stripe,
  then copy the (possibly new) `price_...` into `.env`.

## Checklist

- [ ] Product created with a recurring price, $7.99/month
- [ ] `price_...` copied into `.env`
- [ ] Secret key (`sk_...`) copied into `.env`
- [ ] Webhook endpoint `https://<domain>/webhook` added with the 3 events
- [ ] Signing secret (`whsec_...`) copied into `.env`
- [ ] `PUBLIC_BASE_URL` set (no trailing slash)
- [ ] Success/cancel pages reachable at `/upgrade/success` and `/upgrade/cancel`
- [ ] Bot + webhook receiver restarted
- [ ] Test checkout with card `4242 4242 4242 4242` → success page → Pro in Telegram
