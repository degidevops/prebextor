import { Type } from "typebox";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { execSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

/**
 * Prebextor pi extension — register prebextor_search & prebextor_extract
 * as first-class tools callable by the LLM.
 *
 * Installation:
 *   mkdir -p ~/.pi/agent/extensions/prebextor/
 *   cp index.ts ~/.pi/agent/extensions/prebextor/
 *
 * Requires:
 *   - Prebextor installed (pip install -e /path/to/prebextor)
 *   - SEARXNG_URL env var (for search, bisa dari ~/.hermes/.env)
 *   - CamoFox CLI on PATH (for extract)
 */

// ---- env loader (Hermes compatible) ----

function loadEnvFile(filePath: string): Record<string, string> {
	const result: Record<string, string> = {};
	try {
		if (!existsSync(filePath)) return result;
		const content = readFileSync(filePath, "utf-8");
		for (const line of content.split("\n")) {
			const trimmed = line.trim();
			if (!trimmed || trimmed.startsWith("#")) continue;
			const eqIdx = trimmed.indexOf("=");
			if (eqIdx === -1) continue;
			const key = trimmed.slice(0, eqIdx).trim();
			let val = trimmed.slice(eqIdx + 1).trim();
			// Strip surrounding quotes
			if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
				val = val.slice(1, -1);
			}
			result[key] = val;
		}
	} catch {}
	return result;
}

function buildEnv(): Record<string, string> {
	const env = { ...process.env };
	
	// Load from ~/.hermes/.env (for SEARXNG_URL)
	const home = env.HOME || homedir();
	const hermesEnv = loadEnvFile(join(home, ".hermes", ".env"));
	for (const [k, v] of Object.entries(hermesEnv)) {
		if (!env[k]) env[k] = v; // Don't override existing env
	}
	
	// Also load from ~/.pi/.env
	const piEnv = loadEnvFile(join(home, ".pi", ".env"));
	for (const [k, v] of Object.entries(piEnv)) {
		if (!env[k]) env[k] = v;
	}
	
	return env;
}

// ---- helpers ----

const PREBEXTOR_CMD = "prebextor";

function findPrebextor(): string {
	try {
		execSync("which prebextor", { stdio: "ignore" });
		return "prebextor";
	} catch {
		// Fallback to venv
		const home = process.env.HOME || "/home/degi";
		const venvPaths = [
			`${home}/project/prebextor/.venv/bin/prebextor`,
			`${home}/.local/bin/prebextor`,
		];
		for (const p of venvPaths) {
			try {
				execSync(`test -x "${p}"`, { stdio: "ignore" });
				return p;
			} catch {}
		}
		return "prebextor"; // fallback, will fail gracefully
	}
}

function execPrebextor(args: string[]): string {
	const cmd = findPrebextor();
	const env = buildEnv();
	try {
		return execSync(`${cmd} ${args.join(" ")}`, {
			encoding: "utf-8",
			timeout: 60000,
			maxBuffer: 10 * 1024 * 1024,
			env,
		});
	} catch (e: any) {
		if (e.stdout) return e.stdout;
		throw new Error(`prebextor failed: ${e.message}`);
	}
}

// ---- extension ----

export default function prebextorExtension(pi: ExtensionAPI) {
	// ── prebextor_search ──
	pi.registerTool({
		name: "prebextor_search",
		label: "Web Search",
		description:
			"Search the web via Prebextor (SearXNG backend). " +
			"Returns title, URL, and description for each result. " +
			"Use this for questions that need up-to-date or real-time information from the internet.",
		promptSnippet: "Search the web using Prebextor/SearXNG",
		promptGuidelines: [
			"Use prebextor_search when the user asks for current news, real-time data, or information you don't have in your training data.",
			"Use prebextor_extract after prebextor_search to get full content from interesting result URLs.",
		],
		parameters: Type.Object({
			query: Type.String({
				description: "Search query",
			}),
			limit: Type.Optional(
				Type.Integer({
					description: "Maximum number of results (1-20, default: 5)",
					minimum: 1,
					maximum: 20,
					default: 5,
				}),
			),
		}),
		required: ["query"],
		async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
			const query = params.query as string;
			const limit = (params.limit as number) || 5;
			const raw = execPrebextor(["search", JSON.stringify(query), "--limit", String(limit)]);
			const result = JSON.parse(raw);

			if (!result.success) {
				return {
					content: [
						{
							type: "text",
							text: `Search failed: ${result.error || "unknown error"}`,
						},
					],
					details: { error: result.error },
					isError: true,
				};
			}

			const web = result.data?.web || [];
			if (web.length === 0) {
				return {
					content: [{ type: "text", text: "No results found." }],
					details: { query, results: [] },
				};
			}

			// Format markdown output
			const lines = [`## Search Results: ${query}\n`];
			for (const r of web) {
				lines.push(`### ${r.position}. [${r.title}](${r.url})`);
				lines.push(`${r.description || "*No description*"}\n`);
			}

			return {
				content: [{ type: "text", text: lines.join("\n") }],
				details: { query, results: web },
			};
		},
	});

	// ── prebextor_extract ──
	pi.registerTool({
		name: "prebextor_extract",
		label: "Web Extract",
		description:
			"Extract clean content from one or more URLs via Prebextor deterministic engine. " +
			"Returns clean markdown with XML boundary tags. " +
			"Use this after prebextor_search to get full article content.",
		promptSnippet: "Extract clean content from URLs",
		promptGuidelines: [
			"Use prebextor_extract to get full article content from search result URLs.",
			"Can extract up to 3 URLs at once.",
		],
		parameters: Type.Object({
			urls: Type.Array(Type.String({ description: "URLs to extract" }), {
				description: "URLs to extract content from (max 3)",
				maxItems: 3,
			}),
			scroll_to_bottom: Type.Optional(
				Type.Boolean({
					description: "Scroll to bottom to trigger lazy-loaded content",
					default: false,
				}),
			),
		}),
		required: ["urls"],
		async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
			const urls = params.urls as string[];
			const scroll = (params.scroll_to_bottom as boolean) || false;

			const args = ["extract", ...urls.map((u) => JSON.stringify(u))];
			if (scroll) args.push("--scroll");

			const raw = execPrebextor(args);
			const result = JSON.parse(raw);

			if (!result.success) {
				return {
					content: [{ type: "text", text: `Extraction failed: ${result.error || "unknown error"}` }],
					details: { error: result.error },
					isError: true,
				};
			}

			const data = result.data || [];
			const parts: string[] = [];
			for (const item of data) {
				if (item.error) {
					parts.push(`### ❌ ${item.url}\n${item.error}\n`);
				} else {
					parts.push(
						`### 📄 ${item.title || item.url}\n\n${item.content || "*No content*"}\n`,
					);
				}
			}

			return {
				content: [{ type: "text", text: parts.join("\n---\n") }],
				details: { results: data },
			};
		},
	});
}