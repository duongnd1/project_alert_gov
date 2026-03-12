import axios from 'axios';
import * as cheerio from 'cheerio';
import chalk from 'chalk';
import { GoogleGenerativeAI } from '@google/generative-ai';
import dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';

dotenv.config({ path: '.env.local' });
dotenv.config({ path: '.env' });

// ============================================================
// TYPES
// ============================================================

export interface ScrapedArticle {
    title: string;
    content: string;     // Plain text
    htmlContent: string; // Raw HTML of article body
    images: string[];
    sourceUrl: string;
    publishedAt?: string;
    author?: string;
    siteName?: string;
}

export interface ProcessedArticle {
    title: string;
    content: string;     // Final HTML content (Vietnamese)
    excerpt: string;
    tags: string[];
    category: string;
    quality_score: number;
    source_language: string;
    target_language: string;
    source_url: string;
    scraped_images: string[];
    pipeline_time_ms: number;
}

// ============================================================
// SECTION 1 — WEB SCRAPER (axios + cheerio)
// ============================================================

async function scrapeArticle(url: string): Promise<ScrapedArticle> {
    console.log(chalk.blue(`\n🌐 Scraping: ${url}`));

    const response = await axios.get(url, {
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,vi;q=0.7',
        },
        timeout: 15000,
        maxRedirects: 5,
    });

    const $ = cheerio.load(response.data);
    const hostname = new URL(url).hostname;

    let article: ScrapedArticle;
    if (hostname.includes('36kr.com')) article = parse36kr($, url);
    else if (hostname.includes('gamelook.com.cn')) article = parseGamelook($, url);
    else if (hostname.includes('17173.com')) article = parse17173($, url);
    else if (hostname.includes('gamersky.com')) article = parseGamersky($, url);
    else article = parseGeneric($, url);

    article.content = article.content.replace(/\s+/g, ' ').trim();
    article.title = article.title.trim();

    console.log(chalk.green(`   ✅ Scraped: "${article.title}"`));
    console.log(chalk.gray(`   Content: ${article.content.length} chars | Images: ${article.images.length}`));

    if (article.content.length < 100) {
        console.log(chalk.yellow(`   ⚠️  Warning: Short content. Parser may need adjustment for this site.`));
    }
    return article;
}

function extractImages($: cheerio.CheerioAPI, $container: cheerio.Cheerio<any>, baseUrl: string): string[] {
    const images: string[] = [];
    $container.find('img').each((_: number, el: any) => {
        const src = $(el).attr('src') || $(el).attr('data-src') || $(el).attr('data-original');
        if (src && !src.includes('icon') && !src.includes('logo') && !src.includes('avatar') && !src.includes('emoji')) {
            images.push(src.startsWith('http') ? src : new URL(src, baseUrl).href);
        }
    });
    return images;
}

function parseGeneric($: cheerio.CheerioAPI, url: string): ScrapedArticle {
    const titleSelectors = ['h1.article-title', 'h1.post-title', 'h1.entry-title', 'article h1', '.article h1', '.content h1', 'h1[itemprop="headline"]', 'h1'];
    const contentSelectors = ['.rich_media_content', '#js_content', 'article .content', 'article .entry-content', '.article-content', '.post-content', '.entry-content', '.article-body', '.article__body', '.story-body', '.news-content', '[itemprop="articleBody"]', '.text-content', 'article'];

    let title = '';
    for (const sel of titleSelectors) {
        const found = $(sel).first().text().trim();
        if (found && found.length > 5) { title = found; break; }
    }
    if (!title) title = $('meta[property="og:title"]').attr('content') || $('title').text().trim() || 'Untitled';

    let $content: cheerio.Cheerio<any> | null = null;
    for (const sel of contentSelectors) {
        const found = $(sel).first();
        if (found.length && found.text().trim().length > 100) { $content = found; break; }
    }
    if ($content) $content.find('script,style,nav,.ad,.advertisement,.social-share,.related-posts,.comments,footer').remove();

    return {
        title,
        content: $content ? $content.text() : $('body').text().substring(0, 5000),
        htmlContent: $content ? $content.html() || '' : '',
        images: $content ? extractImages($, $content, url) : [],
        sourceUrl: url,
        author: $('meta[name="author"]').attr('content') || undefined,
        publishedAt: $('meta[property="article:published_time"]').attr('content') || undefined,
        siteName: $('meta[property="og:site_name"]').attr('content') || new URL(url).hostname,
    };
}

function parse36kr($: cheerio.CheerioAPI, url: string): ScrapedArticle {
    const title = $('h1.article-title').text().trim() || $('h1').first().text().trim() || 'Untitled';
    const $c = $('.article-content').first();
    $c.find('script,style,.ad').remove();
    return { title, content: $c.text(), htmlContent: $c.html() || '', images: extractImages($, $c, url), sourceUrl: url, siteName: '36Kr' };
}

function parseGamelook($: cheerio.CheerioAPI, url: string): ScrapedArticle {
    const title = $('h1.entry-title').text().trim() || $('h1').first().text().trim() || 'Untitled';
    const $c = $('.entry-content').first();
    $c.find('script,style,.ad,.sharedaddy').remove();
    return { title, content: $c.text(), htmlContent: $c.html() || '', images: extractImages($, $c, url), sourceUrl: url, siteName: 'GameLook', publishedAt: $('time.entry-date').attr('datetime') || undefined };
}

function parse17173($: cheerio.CheerioAPI, url: string): ScrapedArticle {
    const title = $('h1#newsTitle').text().trim() || $('h1').first().text().trim() || 'Untitled';
    const $c = ($('#newsContent').first().length ? $('#newsContent') : $('.article-body')).first();
    $c.find('script,style,.ad').remove();
    return { title, content: $c.text(), htmlContent: $c.html() || '', images: extractImages($, $c, url), sourceUrl: url, siteName: '17173' };
}

function parseGamersky($: cheerio.CheerioAPI, url: string): ScrapedArticle {
    const $c = ($('.Mid2L_con .Mid2L_ctt').first().length ? $('.Mid2L_con .Mid2L_ctt') : $('article')).first();
    $c.find('script,style,.ad,.gs_nc_editor').remove();
    return { title: $('h1').first().text().trim() || 'Untitled', content: $c.text(), htmlContent: $c.html() || '', images: extractImages($, $c, url), sourceUrl: url, siteName: 'Gamersky' };
}

// ============================================================
// SECTION 2 — AI PROMPTS
// ============================================================

const ANALYST_PROMPT = `You are an expert content analyst specializing in gaming industry news.
Extract the "DNA" of the article — essential facts, context, and structure.
Source may be in Chinese (中文), English, or mixed. You must understand ALL languages.

Return JSON with this exact structure:
{
  "headline": "Core headline in one sentence (English)",
  "facts": ["fact1", "fact2", ...],
  "entities": { "games": [], "companies": [], "people": [] },
  "category": "one of: Reviews | Industry | Esports | Mobile | PC | Console | Updates | Releases",
  "tone": "the tone of the original",
  "key_quotes": ["important direct quotes"],
  "context": "brief background context",
  "source_language": "zh-CN | en | other"
}`;

const WRITER_PROMPT_VI = `Bạn là một chuyên gia phân tích ngành game kiêm biên tập viên cấp cao, viết bài tóm tắt sâu sắc dành riêng cho Telegram. Phong cách: chuyên nghiệp, phân tích sắc bén, làm nổi bật được bản chất vấn đề (insight), nhưng vẫn trình bày trực quan, đẹp mắt và dễ đọc.

NHIỆM VỤ: Dựa trên phân tích DNA, viết lại thành bản tin Tiếng Việt chất lượng cao. ĐỘ DÀI MỤC TIÊU: Khoảng 300 - 400 từ (phù hợp để đọc sâu nhưng không quá dài).

QUY TẮC BẮT BUỘC:
1. KHÔNG dịch máy móc hay tóm tắt hời hợt. Hãy chiết xuất những điểm ĐẶC SẮC NHẤT và CỐT LÕI NHẤT của bài viết. Giữ nguyên thuật ngữ ngành, tên Tiếng Anh/Tiếng Trung của Game/Công ty.
2. CẤU TRÚC BÀI VIẾT (Rất quan trọng để tối ưu cho Telegram):
   - Đoạn 1 (Tiêu điểm): 2-3 câu mở đầu khái quát toàn cảnh, đi thẳng vào vấn đề chính. Dùng 1 emoji phù hợp để mở đầu.
   - Đoạn 2 (Chi tiết & Dữ liệu): Dùng danh sách gạch đầu dòng (Bắt đầu bằng gạch ngang và Emoji: - 💰...). Trình bày các fact, số liệu, tên game/công ty. Khoảng 4-6 gạch đầu dòng chứa thông tin "đặc".
   - Đoạn 3 (Góc nhìn / Insight): Phân tích tác động, xu hướng hoặc bài học rút ra từ tin tức này đối với thị trường game (Trung Quốc/Global). Viết khoảng 3-4 câu sâu sắc.
3. ĐỊNH DẠNG HTML (QUAN TRỌNG): 
   - CHỈ SỬ DỤNG thẻ HTML của Telegram: <b>in đậm</b>, <i>in nghiêng</i>, <u>gạch chân</u>. 
   - TUYỆT ĐỐI KHÔNG dùng Markdown (*, **, #) vì sẽ gây lỗi hiển thị.

OUTPUT (JSON):
{
  "title": "Plain text title, no HTML tags, no Markdown, giật tít chuyên nghiệp, tối đa 14 chữ",
  "content": "Bản tin hoàn chỉnh (~300-400 từ) tuân thủ cấu trúc 3 phần. Sử dụng <b>, <i> và NHIỀU EMOJI. Căn lề rõ ràng.",
  "excerpt": "Tóm tắt 1 câu cốt lõi nhất cho Notification",
  "tags": ["tag1", "tag2"]
}`;

const EDITOR_PROMPT = `You are a senior editor at a gaming news publication.
Review the article for: Accuracy, Readability, Length, Tone.
IMPORTANT: You MUST perfectly preserve ALL Emojis, bullet points (-), and HTML tags (<b>, <i>, <u>) from the original draft. DO NOT strip the formatting! DO NOT rewrite into plain paragraphs.

Return JSON:
{
  "quality_score": 0.0 to 1.0,
  "verdict": "pass" | "needs_revision" | "fail",
  "issues": [{"type": "...", "severity": "low|medium|high", "description": "...", "suggestion": "..."}],
  "revised_content": "Full revised content (or original if no changes)",
  "revised_title": "Revised title or original",
  "revised_excerpt": "Revised excerpt or original"
}
ALWAYS return revised_content, revised_title, revised_excerpt even if unchanged.`;

// ============================================================
// SECTION 3 — AI PROVIDER
// ============================================================

interface AIResponse { text: string; model: string; }

class GeminiProvider {
    private genAI: GoogleGenerativeAI;
    readonly modelName: string;
    private maxRetries = 3;
    private baseDelay = 45000;

    constructor(apiKey: string, model?: string) {
        this.genAI = new GoogleGenerativeAI(apiKey);
        // Using gemini-2.5-flash since it's the target default now
        this.modelName = model || 'gemini-2.5-flash';
    }

    private async withRetry<T>(fn: () => Promise<T>, label: string): Promise<T> {
        for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
            try { return await fn(); } catch (error: any) {
                const isRateLimit = error?.status === 429 || error?.message?.includes('429') || error?.message?.includes('RESOURCE_EXHAUSTED');
                if (isRateLimit && attempt < this.maxRetries) {
                    const retryMatch = error?.message?.match(/retryDelay.*?(\d+)s/);
                    const waitSec = retryMatch ? parseInt(retryMatch[1]) + 5 : (this.baseDelay / 1000) * (attempt + 1);
                    console.log(`   ⏳ Rate limited (attempt ${attempt + 1}). Waiting ${waitSec}s...`);
                    await new Promise(r => setTimeout(r, waitSec * 1000));
                } else throw error;
            }
        }
        throw new Error(`Failed after ${this.maxRetries} retries for ${label}`);
    }

    async generateJSON<T>(systemPrompt: string, userPrompt: string): Promise<T> {
        return this.withRetry(async () => {
            const model = this.genAI.getGenerativeModel({
                model: this.modelName,
                systemInstruction: systemPrompt,
                generationConfig: { responseMimeType: 'application/json' }
            });
            const result = await model.generateContent(userPrompt);
            const text = result.response.text();
            try { return JSON.parse(text) as T; } catch {
                const m = text.match(/```(?:json)?\s*([\s\S]*?)```/);
                if (m) return JSON.parse(m[1].trim()) as T;
                throw new Error(`Failed to parse JSON: ${text.substring(0, 200)}`);
            }
        }, 'generateJSON');
    }
}

// ============================================================
// SECTION 4 — PIPELINE ORCHESTRATOR
// ============================================================

export interface PipelineOptions {
    url: string;
    targetLanguage?: 'vi' | 'en';
    skipEditor?: boolean;
    customPrompt?: string | null;
    onComplete?: (article: ProcessedArticle) => Promise<void>;
}

export async function runPipeline(opts: PipelineOptions): Promise<ProcessedArticle> {
    const { url, targetLanguage = 'vi', skipEditor = false, customPrompt } = opts;
    const startTotal = Date.now();

    const scraped = await scrapeArticle(url);
    if (!scraped.content || scraped.content.length < 50) {
        throw new Error(`Scraping failed or returned too little content for: ${url}`);
    }

    const aiProvider = process.env.AI_PROVIDER || 'gemini';
    const apiKey = aiProvider === 'openai' ? process.env.OPENAI_API_KEY! : process.env.GEMINI_API_KEY!;
    if (!apiKey) throw new Error(`Missing API key for provider: ${aiProvider}`);
    const ai = new GeminiProvider(apiKey);
    console.log(chalk.gray(`🤖 AI Provider: ${aiProvider} (${ai.modelName})`));

    console.log(chalk.yellow('\n📊 Step 1/3: Analyzing article DNA...'));
    const t1 = Date.now();
    const dna = await ai.generateJSON<any>(ANALYST_PROMPT, `Analyze this article:\n\n${scraped.content.substring(0, 15000)}`);
    console.log(chalk.green(`   ✅ DNA extracted (${Date.now() - t1}ms)`));

    console.log(chalk.yellow(`\n✍️  Step 2/3: Writing ${targetLanguage === 'vi' ? 'Vietnamese' : 'English'} article...`));
    const t2 = Date.now();
    let writerSystemPrompt = WRITER_PROMPT_VI;
    if (customPrompt) {
        console.log(chalk.magenta(`   🎯 Custom Prompt: "${customPrompt}"`));
        writerSystemPrompt += `\n\n[YÊU CẦU ĐẶC BIỆT TỪ NGƯỜI DÙNG]:\n${customPrompt}`;
    }
    const written = await ai.generateJSON<any>(writerSystemPrompt, `DNA analysis:\n\n${JSON.stringify(dna, null, 2)}`);
    console.log(chalk.green(`   ✅ Article written (${Date.now() - t2}ms) — ${written.content?.length} chars`));

    let finalTitle = written.title;
    let finalContent = written.content;
    let finalExcerpt = written.excerpt;
    let qualityScore = 1.0;

    if (!skipEditor) {
        console.log(chalk.yellow('\n🔍 Step 3/3: Editor review...'));
        const t3 = Date.now();
        const review = await ai.generateJSON<any>(EDITOR_PROMPT, `Review:\n\n${JSON.stringify({ dna_analysis: dna, article: { title: written.title, content: written.content, excerpt: written.excerpt }, target_language: targetLanguage }, null, 2)}`);
        console.log((review.verdict === 'pass' ? chalk.green : chalk.yellow)(`   ${review.verdict?.toUpperCase()} (Score: ${review.quality_score}) — (${Date.now() - t3}ms)`));
        finalTitle = review.revised_title || written.title;
        finalContent = review.revised_content || written.content;
        finalExcerpt = review.revised_excerpt || written.excerpt;
        qualityScore = review.quality_score;
    }

    const result: ProcessedArticle = {
        title: finalTitle,
        content: finalContent,
        excerpt: finalExcerpt,
        tags: written.tags || [],
        category: dna.category || 'Industry',
        quality_score: qualityScore,
        source_language: dna.source_language || 'zh-CN',
        target_language: targetLanguage,
        source_url: url,
        scraped_images: scraped.images,
        pipeline_time_ms: Date.now() - startTotal,
    };

    console.log(chalk.cyan(`\n⏱️  Total: ${(result.pipeline_time_ms / 1000).toFixed(1)}s`));

    if (opts.onComplete) {
        await opts.onComplete(result);
    }

    return result;
}

// ============================================================
// CLI ENTRY POINT
// ============================================================
async function main() {
    const args = process.argv.slice(2);
    const urlIndex = args.indexOf('--url');
    const url = urlIndex !== -1 ? args[urlIndex + 1] : null;

    const promptIndex = args.indexOf('--prompt');
    const customPrompt = promptIndex !== -1 ? args[promptIndex + 1] : null;

    if (!url) {
        process.exit(0);
    }

    await runPipeline({
        url,
        customPrompt,
        targetLanguage: 'vi',
        skipEditor: false,
        onComplete: async (article) => {
            // Write to a temporary JSON file so Python can read the structured result
            const outputObj = {
                title: article.title,
                content: article.content,
                excerpt: article.excerpt,
                tags: article.tags,
                source_url: article.source_url
            };
            const tempFile = path.join(process.cwd(), 'ai_news_output.json');
            fs.writeFileSync(tempFile, JSON.stringify(outputObj, null, 2), 'utf8');
        }
    });

    process.exit(0);
}

main().catch(e => { console.error(chalk.red(`\n❌ Fatal: ${e.message}`)); process.exit(1); });
