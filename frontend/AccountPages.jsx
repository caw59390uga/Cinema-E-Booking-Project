import React, { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, CheckCircle2, CreditCard, LockKeyhole, Mail, UserRound, ShieldCheck, MapPin } from 'lucide-react';
import './account-pages.css';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000/api';
const EMPTY_ADDRESS = { street: '', city: '', state: '', postalCode: '', country: 'USA' };
const ROUTES = {
  register: '/account/register', verify: '/account/verify',
  forgot: '/account/forgot-password', reset: '/account/reset-password',
  profile: '/account/profile',
};

async function api(path, method = 'GET', body, token) {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function useRequest() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const run = useCallback(async (request, success) => {
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await request();
      setMessage(response?.message || success || 'Saved successfully.');
      return response;
    } catch (err) {
      setError(err?.message || 'Unable to complete your request.');
      return null;
    } finally { setBusy(false); }
  }, []);
  return { busy, error, message, run, setMessage, setError };
}

function Notice({ error, message }) {
  return <>
    {error && <p className="account-alert account-alert-error" role="alert">{error}</p>}
    {message && <p className="account-alert account-alert-success" role="status">{message}</p>}
  </>;
}
function Field({ label, name, type = 'text', value, onChange, ...rest }) {
  return <label className="account-field">{label}
    <input name={name} type={type} value={value} onChange={onChange} {...rest} />
  </label>;
}
function Submit({ busy, children }) {
  return <button type="submit" className="account-action" disabled={busy}>{busy ? 'Processing…' : children}</button>;
}
function NavLink({ to, navigate, children }) {
  return <button type="button" className="account-text-link" onClick={() => navigate(to)}>{children}</button>;
}
function Frame({ title, subtitle, children, navigate, icon: Icon = UserRound }) {
  return <div className="account-screen">
    <header className="account-header">
      <button type="button" onClick={() => navigate('/')} className="account-back"><ArrowLeft size={17}/> Movies</button>
      <span className="account-wordmark">CINEMA</span>
    </header>
    <main className="account-panel">
      <div className="account-panel-icon"><Icon size={24} /></div>
      <h1>{title}</h1><p className="account-subtitle">{subtitle}</p>
      {children}
    </main>
  </div>;
}
const input = (setter, obj) => e => setter({ ...obj, [e.target.name]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });

export function RegisterPage({ navigate }) {
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', phone: '', password: '', confirm: '', promo_opt_in: false });
  const [registered, setRegistered] = useState(false);
  const request = useRequest();
  async function submit(e) {
    e.preventDefault();
    if (form.password !== form.confirm) { request.setError('Passwords do not match.'); return; }
    if (form.password.length < 12) { request.setError('Use at least 12 characters for your password.'); return; }
    const { confirm, ...payload } = form;
    const done = await request.run(() => api('/auth/register', 'POST', payload));
    if (done) setRegistered(true);
  }
  return <Frame title="Create your account" subtitle="Join Cinema. Verify your email before signing in." navigate={navigate} icon={UserRound}>
    {!registered ? <form className="account-form" onSubmit={submit}>
      <div className="account-two">
        <Field label="First name" name="first_name" value={form.first_name} onChange={input(setForm, form)} required maxLength={80} autoComplete="given-name" />
        <Field label="Last name" name="last_name" value={form.last_name} onChange={input(setForm, form)} required maxLength={80} autoComplete="family-name" />
      </div>
      <Field label="Email" name="email" type="email" value={form.email} onChange={input(setForm, form)} required maxLength={254} autoComplete="email" />
      <Field label="Phone (optional)" name="phone" type="tel" value={form.phone} onChange={input(setForm, form)} maxLength={30} autoComplete="tel" />
      <Field label="Password (12+ characters)" name="password" type="password" value={form.password} onChange={input(setForm, form)} minLength={12} maxLength={128} required autoComplete="new-password" />
      <Field label="Confirm password" name="confirm" type="password" value={form.confirm} onChange={input(setForm, form)} required autoComplete="new-password" />
      <label className="account-checkbox"><input type="checkbox" name="promo_opt_in" checked={form.promo_opt_in} onChange={input(setForm, form)} /> Email me offers and promotions (optional)</label>
      <Notice {...request} /><Submit busy={request.busy}>Create account</Submit>
    </form> : <div className="account-form"><div className="account-confirm-icon"><Mail /></div><Notice {...request}/><p>We sent a verification link to <strong>{form.email}</strong>. It expires after 24 hours.</p>
      <NavLink to={ROUTES.verify} navigate={navigate}>Already have a verification link?</NavLink>
    </div>}
    <div className="account-links"><NavLink to="/login" navigate={navigate}>Already registered? Sign in</NavLink><NavLink to={ROUTES.verify} navigate={navigate}>Verify or resend email</NavLink></div>
  </Frame>;
}

export function VerifyPage({ navigate }) {
  const tokenFromLink = new URLSearchParams(window.location.search).get('token') || '';
  const [token, setToken] = useState(tokenFromLink);
  const [email, setEmail] = useState('');
  const request = useRequest();
  async function verify(e) {
    e.preventDefault();
    const ok = await request.run(() => api('/auth/verify', 'POST', { token }));
    if (ok) setToken('');
  }
  async function resend(e) {
    e.preventDefault();
    await request.run(() => api('/auth/resend-verification', 'POST', { email }));
  }
  return <Frame title="Verify your email" subtitle="Enter your verification token or follow the link sent to your inbox." navigate={navigate} icon={ShieldCheck}>
    <form className="account-form" onSubmit={verify}>
      <Field label="Verification token" name="token" value={token} onChange={e=>setToken(e.target.value)} required autoComplete="off" />
      <Notice {...request}/><Submit busy={request.busy}>Verify account</Submit>
    </form>
    <form className="account-form account-form-secondary" onSubmit={resend}>
      <h2>Need a new link?</h2>
      <Field label="Registration email" name="email" type="email" value={email} onChange={e=>setEmail(e.target.value)} required />
      <Submit busy={request.busy}>Resend verification</Submit>
    </form>
    <div className="account-links"><NavLink to="/login" navigate={navigate}>Continue to login</NavLink></div>
  </Frame>;
}

export function ForgotPasswordPage({ navigate }) {
  const [email, setEmail] = useState('');
  const request = useRequest();
  return <Frame title="Forgot password?" subtitle="We'll send a reset link if the email belongs to an account." navigate={navigate} icon={Mail}>
    <form className="account-form" onSubmit={e=>{e.preventDefault();request.run(()=>api('/auth/forgot-password','POST',{email}));}}>
      <Field label="Email address" name="email" type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="email" />
      <Notice {...request}/><Submit busy={request.busy}>Send reset link</Submit>
    </form>
    <div className="account-links"><NavLink to={ROUTES.reset} navigate={navigate}>Already have a reset token?</NavLink><NavLink to="/login" navigate={navigate}>Return to login</NavLink></div>
  </Frame>;
}

export function ResetPasswordPage({ navigate }) {
  const [token, setToken] = useState(new URLSearchParams(window.location.search).get('token') || '');
  const [passwords, setPasswords] = useState({ new_password: '', confirm: '' });
  const request = useRequest();
  const [done, setDone] = useState(false);
  async function submit(e) {
    e.preventDefault();
    if (passwords.new_password !== passwords.confirm) { request.setError('Passwords do not match.'); return; }
    const ok = await request.run(() => api('/auth/reset-password','POST',{token,new_password:passwords.new_password}));
    if (ok) { setDone(true);setToken('');setPasswords({new_password:'',confirm:''}); }
  }
  return <Frame title="Set a new password" subtitle="Reset tokens expire after one hour and can only be used once." navigate={navigate} icon={LockKeyhole}>
    {!done && <form className="account-form" onSubmit={submit}>
      <Field label="Reset token" name="token" value={token} onChange={e=>setToken(e.target.value)} required />
      <Field label="New password" name="new_password" type="password" minLength={12} maxLength={128} required autoComplete="new-password" value={passwords.new_password} onChange={input(setPasswords, passwords)} />
      <Field label="Confirm new password" name="confirm" type="password" required autoComplete="new-password" value={passwords.confirm} onChange={input(setPasswords, passwords)} />
      <Notice {...request}/><Submit busy={request.busy}>Reset password</Submit>
    </form>}
    {done && <div className="account-form"><Notice {...request}/><NavLink navigate={navigate} to="/login">Sign in with your new password</NavLink></div>}
    <div className="account-links"><NavLink to={ROUTES.forgot} navigate={navigate}>Request another reset link</NavLink></div>
  </Frame>;
}

function ChangePasswordForm({ userId, token, onPasswordChanged }) {
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '', confirm: '' });
  const request = useRequest();
  async function submit(e) {
    e.preventDefault();
    if (passwords.new_password !== passwords.confirm) { request.setError('New passwords do not match.'); return; }
    const response = await request.run(() => api(`/users/${encodeURIComponent(userId)}/change-password`, 'POST', {current_password:passwords.current_password,new_password:passwords.new_password},token));
    if (response) {setPasswords({current_password:'',new_password:'',confirm:''}); onPasswordChanged?.();}
  }
  return <section className="account-section"><h2>Change password</h2>
    <form className="account-form" onSubmit={submit}>
      <Field label="Current password" name="current_password" type="password" value={passwords.current_password} onChange={input(setPasswords, passwords)} required autoComplete="current-password" />
      <Field label="New password (12+ characters)" name="new_password" type="password" minLength={12} maxLength={128} value={passwords.new_password} onChange={input(setPasswords, passwords)} required autoComplete="new-password" />
      <Field label="Confirm new password" name="confirm" type="password" value={passwords.confirm} onChange={input(setPasswords, passwords)} required autoComplete="new-password" />
      <Notice {...request}/><Submit busy={request.busy}>Update password</Submit>
    </form>
  </section>;
}

export function ProfilePage({ navigate, token, onPasswordChanged }) {
  const [profile, setProfile] = useState(null);
  const [editing, setEditing] = useState(null);
  const [card, setCard] = useState({card_number:'',card_type:'Visa',expiration_date:''});
  const [loading, setLoading] = useState(true);
  const request = useRequest();
  const reload = useCallback(async (userId) => {
    const result = await api(`/users/${encodeURIComponent(userId)}`,'GET',null,token);
    setProfile(result); return result;
  },[token]);
  // Identity comes ONLY from the verified /auth/me endpoint, never from a user ID in the URL.
  useEffect(() => {
    let live = true;
    if (!token) {setLoading(false);return;}
    (async()=>{try{
      const me = await api('/auth/me','GET',null,token);
      if (live) {setProfile(me.user);setEditing(null);}
    }catch(e){if(live)request.setError(e.message)}finally{if(live)setLoading(false)}})();
    return ()=>{live=false};
  },[token]);
  const userId = profile?.user_id;
  const change = useCallback((e) => setEditing(current=>({...current,[e.target.name]:e.target.type==='checkbox'?e.target.checked:e.target.value})),[]);
  async function saveProfile(e) {
    e.preventDefault();
    const data = {first_name:editing.first_name,last_name:editing.last_name,phone:editing.phone,promo_opt_in:editing.promo_opt_in,address:editing.address};
    const r = await request.run(()=>api(`/users/${encodeURIComponent(userId)}/profile`,'PUT',data,token));
    if (r) { setProfile(r.user);setEditing(null); }
  }
  async function addCard(e) {
    e.preventDefault();
    const result = await request.run(()=>api(`/users/${encodeURIComponent(userId)}/cards`,'POST',card,token));
    if (result) {setProfile(result.user);setCard({card_number:'',card_type:'Visa',expiration_date:''});}
  }
  async function deleteCard(id) {
    const r = await request.run(()=>api(`/users/${encodeURIComponent(userId)}/cards/${encodeURIComponent(id)}`,'DELETE',null,token));
    if (r) setProfile(r.user);
  }
  return <Frame title="My profile" subtitle="Your account details, address, saved payment methods, and security." navigate={navigate} icon={UserRound}>
    {!token && <div className="account-alert account-alert-error">Sign in first. Your teammate's login/useAuth flow must provide an access token before a private profile can be opened.</div>}
    {loading && <p>Loading profile…</p>}
    <Notice {...request}/>
    {profile && <div className="account-profile">
      <section className="account-section"><div className="account-section-heading"><h2>Personal information</h2><button type="button" onClick={()=>setEditing(editing?null:{...profile,address:{...EMPTY_ADDRESS,...(profile.address||{})}})}>{editing?'Cancel':'Edit'}</button></div>
        {!editing ? <div className="account-details">
          <span>Name</span><strong>{profile.first_name} {profile.last_name}</strong>
          <span>Email (read-only)</span><strong>{profile.email}</strong>
          <span>Phone</span><strong>{profile.phone||'Not provided'}</strong>
          <span>Status</span><strong>{profile.status}</strong>
          <span>Offers</span><strong>{profile.promo_opt_in?'Subscribed':'Not subscribed'}</strong>
          <span><MapPin size={14} /> Mailing address</span><strong>{profile.address ? [profile.address.street,profile.address.city,profile.address.state,profile.address.postalCode,profile.address.country].filter(Boolean).join(', ') : 'Not added'}</strong>
        </div> : <form className="account-form" onSubmit={saveProfile}>
          <div className="account-two"><Field label="First name" name="first_name" required maxLength={80} value={editing.first_name} onChange={change}/><Field label="Last name" name="last_name" required maxLength={80} value={editing.last_name} onChange={change}/></div>
          <Field label="Email (cannot be changed)" name="email" type="email" value={profile.email} readOnly />
          <Field label="Phone" name="phone" value={editing.phone||''} onChange={change} maxLength={30}/>
          <h3>Mailing address (one maximum)</h3>
          {Object.keys(EMPTY_ADDRESS).map(k=><Field key={k} label={k==='postalCode'?'Postal code':k[0].toUpperCase()+k.slice(1)} name={k} value={editing.address?.[k]||''} onChange={e=>setEditing({...editing,address:{...editing.address,[k]:e.target.value}})} maxLength={120}/>)}
          <label className="account-checkbox"><input name="promo_opt_in" type="checkbox" checked={!!editing.promo_opt_in} onChange={change}/> Receive promotional emails</label>
          <Submit busy={request.busy}>Save profile</Submit>
        </form>}
      </section>
      <section className="account-section"><h2><CreditCard size={20}/> Saved cards ({(profile.saved_cards||[]).length}/3)</h2>
        <p className="account-note">Only card type, expiry and last four digits are shown. Never enter a CVV.</p>
        {(profile.saved_cards||[]).map(c=><div className="account-card-row" key={c.card_id}>
          <span>{c.card_type} ending in {c.last4} · {c.expiration_date}</span>
          <button type="button" onClick={()=>deleteCard(c.card_id)} disabled={request.busy}>Remove</button>
        </div>)}
        {(profile.saved_cards||[]).length<3 && <form className="account-form" onSubmit={addCard}>
          <Field label="Card number" name="card_number" inputMode="numeric" pattern="[0-9 ]{13,25}" required autoComplete="cc-number" value={card.card_number} onChange={input(setCard,card)} />
          <div className="account-two">
            <label className="account-field">Card type<select value={card.card_type} onChange={e=>setCard({...card,card_type:e.target.value})}><option>Visa</option><option>Mastercard</option><option>Amex</option><option>Discover</option></select></label>
            <Field label="Expiration (MM/YY)" name="expiration_date" placeholder="12/28" pattern="(0[1-9]|1[0-2])/[0-9]{2}" required maxLength={5} autoComplete="cc-exp" value={card.expiration_date} onChange={input(setCard,card)}/>
          </div><Submit busy={request.busy}>Add card</Submit>
        </form>}
        {(profile.saved_cards||[]).length>=3 && <p className="account-note">You've reached the three-card limit. Remove one before adding another.</p>}
      </section>
      <ChangePasswordForm userId={userId} token={token} onPasswordChanged={onPasswordChanged}/>
    </div>}
  </Frame>;
}

/** A small adapter until the teammate's React Router + useAuth are merged.
 * `navigate` is provided by the router adapter; never store auth tokens in this module.
 * `token` must come from the team's authenticated useAuth hook.
 */
export default function AccountPages({ path, navigate, token = null, onPasswordChanged }) {
  if (path === ROUTES.register) return <RegisterPage navigate={navigate}/>;
  if (path === ROUTES.verify) return <VerifyPage navigate={navigate}/>;
  if (path === ROUTES.forgot) return <ForgotPasswordPage navigate={navigate}/>;
  if (path === ROUTES.reset) return <ResetPasswordPage navigate={navigate}/>;
  if (path === ROUTES.profile) return <ProfilePage navigate={navigate} token={token} onPasswordChanged={onPasswordChanged}/>;
  return null;
}
