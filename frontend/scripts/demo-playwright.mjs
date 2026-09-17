import { chromium } from 'playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const FRONTEND_URL = process.env.DEMO_URL || 'http://localhost:5173'
const HEADLESS = (process.env.PW_HEADLESS || 'true').toLowerCase() !== 'false'
const SHOT_DIR = path.resolve(process.cwd(), 'demo-artifacts')

const PROMPTS = [
  'What should leadership prioritize next?',
  'What are the biggest transparency gaps right now?',
  'What would you tell a leadership team in one minute?',
]

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true })
}

async function screenshot(page, name) {
  const file = path.join(SHOT_DIR, name)
  await page.screenshot({ path: file, fullPage: true })
  return file
}

async function clickQuickLink(page, name) {
  const link = page.getByRole('link', { name })
  await link.click()
  await page.waitForTimeout(300)
}

async function run() {
  await ensureDir(SHOT_DIR)

  const browser = await chromium.launch({ headless: HEADLESS })
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()

  try {
    await page.goto(FRONTEND_URL, { waitUntil: 'networkidle', timeout: 30_000 })

    await screenshot(page, '01-home.png')

    // Run ingestion (safe if already ingested).
    const ingestButton = page.getByRole('button', { name: /Run ingestion|Ingesting\.\.\./i })
    await ingestButton.click()
    await page.waitForTimeout(2_000)
    await page.waitForLoadState('networkidle')

    await screenshot(page, '02-after-ingestion.png')

    // Quick link walkthrough
    await clickQuickLink(page, 'Dataset status')
    await screenshot(page, '03-dataset-status.png')

    await clickQuickLink(page, 'Data quality')
    await screenshot(page, '04-data-quality.png')

    await clickQuickLink(page, 'Reference checks')
    await screenshot(page, '05-reference-checks.png')

    await clickQuickLink(page, 'Schema summary')
    await screenshot(page, '06-schema-summary.png')

    await clickQuickLink(page, 'Quarantined files')
    await screenshot(page, '07-quarantined-files.png')

    await clickQuickLink(page, 'Activation Studio')

    const activationButton = page.getByRole('button', { name: /Generate top activations|Generating\.\.\./i })
    await activationButton.click()
    await page.waitForTimeout(1_500)

    await screenshot(page, '08-activation-studio.png')

    await clickQuickLink(page, 'Leadership Chat')

    const textArea = page.locator('textarea.chat-input')
    const askButton = page.getByRole('button', { name: /Ask the Evidence Agent|Thinking\.\.\./i })

    for (let i = 0; i < PROMPTS.length; i += 1) {
      await textArea.fill(PROMPTS[i])
      await askButton.click()
      await page.waitForTimeout(2_000)
      await page.waitForLoadState('networkidle')
      await screenshot(page, `09-chat-prompt-${i + 1}.png`)
    }

    await page.getByRole('link', { name: /Back to top/i }).click()
    await screenshot(page, '10-back-to-top.png')

    console.log('✅ Playwright demo finished.')
    console.log(`Artifacts saved in: ${SHOT_DIR}`)
  } finally {
    await context.close()
    await browser.close()
  }
}

run().catch((err) => {
  const hint = [
    '\nDemo failed. Quick checks:',
    `1) Frontend running at ${FRONTEND_URL}`,
    '2) Backend running at http://localhost:8000',
    '3) If first run, install browser: npx playwright install chromium',
  ].join('\n')

  console.error('❌', err?.message || err)
  console.error(hint)
  process.exit(1)
})
