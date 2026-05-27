'use client';

/**
 * AuthModal — handles all three auth stages in one component:
 *   login  →  register  →  otp (email verification)
 * Uses React Hook Form + Zod for validation.
 * No React Router required — modal is shown inline over the app.
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { X, Eye, EyeOff, Loader2, Shield, Mail, Lock, User } from 'lucide-react';
import { authApi } from '@/lib/authApi';
import { useAuthStore } from '@/store/authStore';

// ── Schemas ───────────────────────────────────────────────────────────────────

const loginSchema = z.object({
  email:    z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
});

const registerSchema = z.object({
  name:             z.string().min(3, 'Name must be at least 3 characters'),
  email:            z.string().email('Enter a valid email'),
  password:         z.string().min(6, 'Password must be at least 6 characters'),
  confirm_password: z.string(),
}).refine((d) => d.password === d.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password'],
});

const otpSchema = z.object({
  otp: z.string().length(6, 'OTP must be 6 digits').regex(/^\d+$/, 'OTP must be numeric only'),
});

type LoginForm    = z.infer<typeof loginSchema>;
type RegisterForm = z.infer<typeof registerSchema>;
type OtpForm      = z.infer<typeof otpSchema>;
type Tab          = 'login' | 'register' | 'otp';

interface Props { onClose: () => void; }

// ── Component ─────────────────────────────────────────────────────────────────

export function AuthModal({ onClose }: Props) {
  const [tab, setTab]               = useState<Tab>('login');
  const [pendingEmail, setPending]  = useState('');
  const [showPass, setShowPass]     = useState(false);
  const [showConf, setShowConf]     = useState(false);
  const [err, setErr]               = useState('');
  const [msg, setMsg]               = useState('');
  const [busy, setBusy]             = useState(false);

  const { setAuth } = useAuthStore();

  const lf = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });
  const rf = useForm<RegisterForm>({ resolver: zodResolver(registerSchema) });
  const of = useForm<OtpForm>({ resolver: zodResolver(otpSchema) });

  const clear = () => { setErr(''); setMsg(''); };

  // ── Submit handlers ────────────────────────────────────────────────────────

  const onLogin = async (d: LoginForm) => {
    clear(); setBusy(true);
    try {
      const res = await authApi.login(d.email, d.password);
      setAuth(res.access_token, res.user);
      onClose();
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  const onRegister = async (d: RegisterForm) => {
    clear(); setBusy(true);
    try {
      await authApi.register(d.name, d.email, d.password, d.confirm_password);
      setPending(d.email);
      setMsg('Account created! Check your email for the 6-digit verification code.');
      setTab('otp');
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  const onOtp = async (d: OtpForm) => {
    clear(); setBusy(true);
    try {
      const res = await authApi.verifyOtp(pendingEmail, d.otp);
      setAuth(res.access_token, res.user);
      onClose();
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  const onResend = async () => {
    clear(); setBusy(true);
    try {
      const res = await authApi.resendOtp(pendingEmail);
      setMsg(res.message);
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  // ── CSS helpers ────────────────────────────────────────────────────────────

  const inp = `w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm
               text-white placeholder-gray-500 focus:outline-none focus:border-blue-500
               transition-colors`;
  const btn = `w-full py-2.5 rounded-lg text-sm font-semibold transition-all bg-blue-600
               hover:bg-blue-500 active:bg-blue-700 text-white disabled:opacity-50
               disabled:cursor-not-allowed flex items-center justify-center gap-2`;
  const errCls = 'text-xs text-red-400 mt-1';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />

      {/* Card */}
      <div className="relative z-10 w-full max-w-[420px] bg-gray-950 border border-gray-800
                      rounded-2xl shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            <span className="text-white font-semibold text-sm">
              {tab === 'login' ? 'Sign In' : tab === 'register' ? 'Create Account' : 'Verify Email'}
            </span>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors p-1">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab bar (login ↔ register) */}
        {tab !== 'otp' && (
          <div className="flex border-b border-gray-800">
            {(['login', 'register'] as const).map((t) => (
              <button key={t} onClick={() => { setTab(t); clear(); }}
                className={`flex-1 py-3 text-sm font-medium transition-colors ${
                  tab === t
                    ? 'text-blue-400 border-b-2 border-blue-500'
                    : 'text-gray-500 hover:text-gray-300'
                }`}>
                {t === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>
        )}

        <div className="px-6 py-5">
          {/* Status banners */}
          {err && (
            <div className="mb-4 bg-red-900/40 border border-red-700/60 text-red-300
                            text-sm px-3 py-2.5 rounded-lg">
              {err}
            </div>
          )}
          {msg && (
            <div className="mb-4 bg-green-900/40 border border-green-700/60 text-green-300
                            text-sm px-3 py-2.5 rounded-lg">
              {msg}
            </div>
          )}

          {/* ── Login ── */}
          {tab === 'login' && (
            <form onSubmit={lf.handleSubmit(onLogin)} className="space-y-4">
              <div>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                  <input {...lf.register('email')} type="email" placeholder="Email address"
                    className={`${inp} pl-10`} autoComplete="email" />
                </div>
                {lf.formState.errors.email && (
                  <p className={errCls}>{lf.formState.errors.email.message}</p>
                )}
              </div>
              <div>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                  <input {...lf.register('password')} placeholder="Password"
                    type={showPass ? 'text' : 'password'}
                    className={`${inp} pl-10 pr-10`} autoComplete="current-password" />
                  <button type="button" onClick={() => setShowPass(!showPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                    {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {lf.formState.errors.password && (
                  <p className={errCls}>{lf.formState.errors.password.message}</p>
                )}
              </div>
              <button type="submit" className={btn} disabled={busy}>
                {busy && <Loader2 className="w-4 h-4 animate-spin" />}
                Sign In on GeoSentinel
              </button>
            </form>
          )}

          {/* ── Register ── */}
          {tab === 'register' && (
            <form onSubmit={rf.handleSubmit(onRegister)} className="space-y-4">
              <div>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                  <input {...rf.register('name')} placeholder="Full name"
                    className={`${inp} pl-10`} />
                </div>
                {rf.formState.errors.name && (
                  <p className={errCls}>{rf.formState.errors.name.message}</p>
                )}
              </div>
              <div>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                  <input {...rf.register('email')} type="email" placeholder="Email address"
                    className={`${inp} pl-10`} />
                </div>
                {rf.formState.errors.email && (
                  <p className={errCls}>{rf.formState.errors.email.message}</p>
                )}
              </div>
              <div>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                  <input {...rf.register('password')} placeholder="Password (min 6 chars)"
                    type={showPass ? 'text' : 'password'}
                    className={`${inp} pl-10 pr-10`} />
                  <button type="button" onClick={() => setShowPass(!showPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                    {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {rf.formState.errors.password && (
                  <p className={errCls}>{rf.formState.errors.password.message}</p>
                )}
              </div>
              <div>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                  <input {...rf.register('confirm_password')} placeholder="Confirm password"
                    type={showConf ? 'text' : 'password'}
                    className={`${inp} pl-10 pr-10`} />
                  <button type="button" onClick={() => setShowConf(!showConf)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                    {showConf ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {rf.formState.errors.confirm_password && (
                  <p className={errCls}>{rf.formState.errors.confirm_password.message}</p>
                )}
              </div>
              <button type="submit" className={btn} disabled={busy}>
                {busy && <Loader2 className="w-4 h-4 animate-spin" />}
                Create Account on GeoSentinel
              </button>
            </form>
          )}

          {/* ── OTP Verification ── */}
          {tab === 'otp' && (
            <div className="space-y-5">
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-500/15 rounded-full flex items-center
                                justify-center mx-auto mb-3">
                  <Mail className="w-8 h-8 text-blue-400" />
                </div>
                <p className="text-gray-400 text-sm">Code sent to</p>
                <p className="text-white font-semibold mt-0.5">{pendingEmail}</p>
              </div>

              <form onSubmit={of.handleSubmit(onOtp)} className="space-y-4">
                <div>
                  <input
                    {...of.register('otp')}
                    placeholder="Enter 6-digit code"
                    maxLength={6}
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    className={`${inp} text-center text-2xl tracking-[0.6em] font-mono`}
                  />
                  {of.formState.errors.otp && (
                    <p className={errCls + ' text-center'}>{of.formState.errors.otp.message}</p>
                  )}
                </div>
                <button type="submit" className={btn} disabled={busy}>
                  {busy && <Loader2 className="w-4 h-4 animate-spin" />}
                  Verify & Activate
                </button>
              </form>

              <div className="text-center pt-1">
                <p className="text-gray-600 text-xs mb-1">Didn&apos;t receive a code?</p>
                <button onClick={onResend} disabled={busy}
                  className="text-blue-400 hover:text-blue-300 text-xs underline
                             underline-offset-2 disabled:opacity-50 transition-colors">
                  Resend OTP
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}