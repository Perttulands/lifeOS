#!/usr/bin/env bun
/**
 * LifeOS Channel for Claude Code
 * 
 * Pushes Oura data, quest updates, and coaching events into a Claude Code session.
 * Two-way: Claude can reply to update quests, log energy, etc.
 * 
 * Architecture:
 *   - Polls LifeOS CLI for data changes (sleep, readiness, quest state)
 *   - Pushes events when thresholds are hit or data arrives
 *   - Exposes reply tools for quest management and energy logging
 *   - HTTP endpoint for external triggers (cron, webhooks)
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import { execSync } from 'child_process'

const LIFEOS_DIR = '/home/polis/projects/lifeOS'
const LIFEOS_BIN = `${LIFEOS_DIR}/.venv/bin/lifeos`

// --- Helpers ---

function runLifeOS(cmd: string): string {
  try {
    return execSync(`cd ${LIFEOS_DIR} && ${LIFEOS_BIN} ${cmd}`, {
      encoding: 'utf-8',
      timeout: 15000,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }
    }).trim()
  } catch (e: any) {
    return `Error: ${e.stderr || e.message}`
  }
}

function runCmd(cmd: string): string {
  try {
    return execSync(cmd, { encoding: 'utf-8', timeout: 10000 }).trim()
  } catch (e: any) {
    return `Error: ${e.stderr || e.message}`
  }
}

// --- MCP Server ---

const mcp = new Server(
  { name: 'lifeos', version: '1.0.0' },
  {
    capabilities: {
      experimental: { 'claude/channel': {} },
      tools: {},
    },
    instructions: `You are connected to LifeOS, Perttu's personal life coaching system.

Events arrive as <channel source="lifeos" type="...">. Types:
- "morning_brief_data": Sleep, readiness, calendar, and quest data for composing a morning brief.
- "quest_update": A quest was completed or expired.
- "oura_alert": Sleep or readiness crossed a threshold (good or bad).
- "coaching_nudge": Time-based nudge (afternoon energy check, evening reflection).
- "webhook": External trigger (CI, calendar change, etc).

Reply tools available:
- lifeos_quest_add: Add a new quest
- lifeos_quest_done: Complete a quest
- lifeos_log: Log energy, mood, or a note
- lifeos_sync: Sync Oura data
- lifeos_brief: Get brief data
- lifeos_status: Quick status check
- lifeos_trends: Get trend analysis
- lifeos_goal_add: Add a goal
- lifeos_goal_review: Review goal progress

When you receive morning_brief_data, compose a warm personal brief and send it to Perttu.
When you receive a coaching_nudge, check in naturally — don't be robotic.
When Perttu tells you about completed tasks, use lifeos_quest_done.
When Perttu mentions things to do, use lifeos_quest_add.`,
  },
)

// --- Tools ---

mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'lifeos_quest_add',
      description: 'Add a quest to the sidekick board',
      inputSchema: {
        type: 'object',
        properties: {
          title: { type: 'string', description: 'Quest title' },
          type: { type: 'string', enum: ['daily', 'weekly', 'epic'], default: 'daily' },
          xp: { type: 'number', description: 'XP reward (default: auto)' },
          tags: { type: 'string', description: 'Comma-separated tags' },
        },
        required: ['title'],
      },
    },
    {
      name: 'lifeos_quest_done',
      description: 'Complete a quest by ID',
      inputSchema: {
        type: 'object',
        properties: {
          quest_id: { type: 'string', description: 'Quest ID to complete' },
        },
        required: ['quest_id'],
      },
    },
    {
      name: 'lifeos_log',
      description: 'Log energy (1-5), mood (1-5), or a note',
      inputSchema: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['energy', 'mood', 'note'] },
          value: { type: 'string', description: 'Value: 1-5 for energy/mood, text for note' },
          note: { type: 'string', description: 'Optional note' },
        },
        required: ['type', 'value'],
      },
    },
    {
      name: 'lifeos_sync',
      description: 'Sync Oura data',
      inputSchema: {
        type: 'object',
        properties: {
          days: { type: 'number', default: 1, description: 'Days to sync' },
        },
      },
    },
    {
      name: 'lifeos_brief',
      description: 'Get brief context data (sleep, readiness, quests, calendar)',
      inputSchema: {
        type: 'object',
        properties: {
          date: { type: 'string', description: 'Date YYYY-MM-DD (default: today)' },
        },
      },
    },
    {
      name: 'lifeos_status',
      description: 'Quick status snapshot',
      inputSchema: { type: 'object', properties: {} },
    },
    {
      name: 'lifeos_trends',
      description: 'Get trend analysis (sleep, readiness patterns)',
      inputSchema: {
        type: 'object',
        properties: {
          days: { type: 'number', default: 14 },
        },
      },
    },
    {
      name: 'lifeos_goal_add',
      description: 'Add a life goal',
      inputSchema: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          target_date: { type: 'string', description: 'YYYY-MM-DD' },
          category: { type: 'string' },
        },
        required: ['title'],
      },
    },
    {
      name: 'lifeos_goal_review',
      description: 'Review all active goals with velocity and predictions',
      inputSchema: { type: 'object', properties: {} },
    },
    {
      name: 'lifeos_quest_board',
      description: 'Get the current quest board',
      inputSchema: { type: 'object', properties: {} },
    },
  ],
}))

mcp.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params
  let result: string

  switch (name) {
    case 'lifeos_quest_add': {
      const tagArgs = args?.tags ? ` --tag ${(args.tags as string).split(',').join(' --tag ')}` : ''
      const xpArg = args?.xp ? ` --xp ${args.xp}` : ''
      const typeArg = args?.type ? ` --type ${args.type}` : ''
      result = runLifeOS(`quest add "${args?.title}"${typeArg}${xpArg}${tagArgs}`)
      break
    }
    case 'lifeos_quest_done':
      result = runLifeOS(`quest done ${args?.quest_id}`)
      break
    case 'lifeos_log': {
      const noteArg = args?.note ? ` --note "${args.note}"` : ''
      result = runLifeOS(`log ${args?.type} "${args?.value}"${noteArg}`)
      break
    }
    case 'lifeos_sync':
      result = runLifeOS(`sync oura --days ${args?.days || 1}`)
      break
    case 'lifeos_brief':
      result = runLifeOS(`brief --format json${args?.date ? ` --date ${args.date}` : ''}`)
      break
    case 'lifeos_status':
      result = runLifeOS('status --format json')
      break
    case 'lifeos_trends':
      result = runLifeOS(`trends --days ${args?.days || 14}`)
      break
    case 'lifeos_goal_add': {
      const dateArg = args?.target_date ? ` --target-date ${args.target_date}` : ''
      const catArg = args?.category ? ` --category ${args.category}` : ''
      result = runLifeOS(`goal add "${args?.title}"${dateArg}${catArg}`)
      break
    }
    case 'lifeos_goal_review':
      result = runLifeOS('goal review')
      break
    case 'lifeos_quest_board':
      result = runLifeOS('quest board')
      break
    default:
      result = `Unknown tool: ${name}`
  }

  return { content: [{ type: 'text', text: result }] }
})

// --- Connect ---

await mcp.connect(new StdioServerTransport())

// --- HTTP endpoint for external triggers ---

const PORT = 8789

Bun.serve({
  port: PORT,
  hostname: '127.0.0.1',
  async fetch(req) {
    const url = new URL(req.url)
    const path = url.pathname

    if (req.method === 'POST' && path === '/morning-brief') {
      // Trigger morning brief flow
      const syncResult = runLifeOS('sync oura')
      const briefData = runLifeOS('brief --format json')
      const questData = runLifeOS('quest state --format json')
      
      const today = new Date().toISOString().split('T')[0]
      const tz = '+02:00' // Helsinki — adjust for DST
      const calendarData = runCmd(
        `gws calendar events list --params '{"calendarId": "primary", "timeMin": "${today}T00:00:00${tz}", "timeMax": "${today}T23:59:59${tz}", "singleEvents": true, "orderBy": "startTime"}' 2>/dev/null`
      )

      await mcp.notification({
        method: 'notifications/claude/channel',
        params: {
          content: JSON.stringify({
            sync: syncResult,
            brief: briefData,
            quests: questData,
            calendar: calendarData,
          }),
          meta: { type: 'morning_brief_data', date: today },
        },
      })
      return new Response('brief triggered')
    }

    if (req.method === 'POST' && path === '/nudge') {
      const body = await req.text()
      await mcp.notification({
        method: 'notifications/claude/channel',
        params: {
          content: body || 'Time for an energy check-in. How are you feeling?',
          meta: { type: 'coaching_nudge' },
        },
      })
      return new Response('nudge sent')
    }

    if (req.method === 'POST' && path === '/webhook') {
      const body = await req.text()
      await mcp.notification({
        method: 'notifications/claude/channel',
        params: {
          content: body,
          meta: { type: 'webhook', path: path },
        },
      })
      return new Response('ok')
    }

    if (req.method === 'GET' && path === '/health') {
      return new Response(JSON.stringify({
        status: 'ok',
        channel: 'lifeos',
        port: PORT,
      }), { headers: { 'Content-Type': 'application/json' } })
    }

    return new Response('Not found', { status: 404 })
  },
})

console.error(`LifeOS channel running on http://127.0.0.1:${PORT}`)
