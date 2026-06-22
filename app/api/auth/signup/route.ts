import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

export const runtime = 'nodejs';

const WINDOW_MS = 10 * 60 * 1000;
const MAX_ATTEMPTS = 5;
const attempts = new Map<string, { count: number; resetAt: number }>();

function isRateLimited(ip: string) {
  const now = Date.now();
  const current = attempts.get(ip);
  if (!current || current.resetAt <= now) {
    attempts.set(ip, { count: 1, resetAt: now + WINDOW_MS });
    return false;
  }
  current.count += 1;
  return current.count > MAX_ATTEMPTS;
}

export async function POST(request: NextRequest) {
  const ip = request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || 'unknown';
  if (isRateLimited(ip)) {
    return NextResponse.json(
      { error: '가입 요청이 너무 많아. 10분 후 다시 시도해줘.' },
      { status: 429 }
    );
  }

  let body: { email?: unknown; password?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: '잘못된 요청이야.' }, { status: 400 });
  }

  const email = typeof body.email === 'string' ? body.email.trim().toLowerCase() : '';
  const password = typeof body.password === 'string' ? body.password : '';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ error: '올바른 이메일 주소를 입력해줘.' }, { status: 400 });
  }
  if (password.length < 6 || password.length > 72) {
    return NextResponse.json({ error: '비밀번호는 6~72자로 입력해줘.' }, { status: 400 });
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceRoleKey) {
    console.error('Signup API: Supabase server environment variables are missing.');
    return NextResponse.json({ error: '서버 회원가입 설정이 완료되지 않았어.' }, { status: 503 });
  }

  const admin = createClient(url, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { error } = await admin.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
    user_metadata: { full_name: email.split('@')[0] },
  });

  if (error) {
    const message = error.message.toLowerCase();
    if (message.includes('already') || message.includes('registered') || message.includes('exists')) {
      return NextResponse.json({ error: '이미 가입된 이메일이야. 로그인해줘.' }, { status: 409 });
    }
    console.error('Signup API createUser error:', error.message);
    return NextResponse.json({ error: '회원가입에 실패했어. 잠시 후 다시 시도해줘.' }, { status: 400 });
  }

  return NextResponse.json({ ok: true }, { status: 201 });
}
