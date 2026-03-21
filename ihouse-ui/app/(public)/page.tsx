'use client';

/**
 * Phase 860 — New Domaniqo Landing Page
 *
 * Complete redesign with splash animation, dark/light toggle,
 * SVG icons, 8 modules, channels, pricing, FAQ.
 * Self-contained nav and footer (PublicNav/PublicFooter hidden via layout).
 *
 * All CSS is scoped under .domaniqo-landing to prevent style leakage
 * into other pages during Next.js client-side navigation.
 */

import { useEffect, useRef } from 'react';

const CSS_CONTENT = `@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@300;400;500;600&family=Manrope:wght@400;500;600;700&display=swap');

.domaniqo-landing{--bg:#F8F6F2;--bg2:#EAE5DE;--fg:#171A1F;--fg2:rgba(23,26,31,.55);--card:#FFFFFF;--card-b:rgba(23,26,31,.06);--card-h:rgba(23,26,31,.03);--mg:#171A1F;--sm:#EAE5DE;--ss:#D6C8B7;--qo:#6B7258;--dm:#334036;--cw:#F8F6F2;--sc:#B56E45;--sage:#8FA39B;--alert:#C45B4A;--glow:#D4956A;--glowb:#DBA57A;--tl:#B5AFA6;--nav-bg:rgba(248,246,242,.92);--nav-b:rgba(23,26,31,.05);--fb:'Manrope',sans-serif;--fi:'Inter',sans-serif;--fe:'Instrument Serif',Georgia,serif;--r:10px;--rl:14px}
.domaniqo-landing[data-theme="dark"]{--bg:#171A1F;--bg2:#1E2127;--fg:#EAE5DE;--fg2:rgba(234,229,222,.45);--card:rgba(234,229,222,.04);--card-b:rgba(234,229,222,.07);--card-h:rgba(234,229,222,.08);--nav-bg:rgba(23,26,31,.92);--nav-b:rgba(234,229,222,.05)}
.domaniqo-landing *,.domaniqo-landing *::before,.domaniqo-landing *::after{box-sizing:border-box;margin:0;padding:0}.domaniqo-landing{-webkit-font-smoothing:antialiased;scroll-behavior:smooth}.domaniqo-landing{font-family:var(--fi);color:var(--fg);background:var(--bg);overflow-x:hidden;transition:background .35s ease,color .35s ease}.domaniqo-landing a{text-decoration:none;color:inherit}.domaniqo-landing button{font-family:var(--fb);cursor:pointer;border:none;background:none}

/* SPLASH */
#sp{position:fixed;inset:0;z-index:10000;background:linear-gradient(165deg,#0C0E11,#171A1F 40%,#1A1D22);display:flex;align-items:center;justify-content:center;flex-direction:column}#sp.m{background:transparent;pointer-events:none}#sp.g{display:none}
.gr{position:absolute;inset:-50%;width:200%;height:200%;pointer-events:none;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");opacity:.5}
@keyframes to{0%{stroke-dashoffset:200;opacity:.51}80%{opacity:.64}100%{stroke-dashoffset:0;opacity:0}}@keyframes tv{0%{stroke-dashoffset:52;opacity:.45}80%{opacity:.56}100%{stroke-dashoffset:0;opacity:0}}@keyframes th{0%{stroke-dashoffset:36;opacity:.45}80%{opacity:.56}100%{stroke-dashoffset:0;opacity:0}}@keyframes ta{0%{stroke-dashoffset:80;opacity:.5}70%{opacity:.56}100%{stroke-dashoffset:0;opacity:0}}@keyframes dr{0%{offset-distance:0%;opacity:0}5%{opacity:.64}85%{opacity:.64}100%{offset-distance:100%;opacity:0}}@keyframes da{0%{offset-distance:0%;opacity:0}8%{opacity:.56}80%{opacity:.56}100%{offset-distance:100%;opacity:0}}@keyframes gf{0%{opacity:0}40%{opacity:.5}100%{opacity:0}}@keyframes sg{0%{filter:drop-shadow(0 0 0 transparent)}50%{filter:drop-shadow(0 0 8px rgba(255,245,230,.3))}100%{filter:drop-shadow(0 0 0 transparent)}}

/* NAV */
.nav{position:fixed;top:0;left:0;right:0;z-index:1000;padding:0 24px;height:64px;display:flex;align-items:center;justify-content:space-between;background:var(--nav-bg);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border-bottom:1px solid var(--nav-b);opacity:0;transform:translateY(-8px);transition:opacity .5s ease,transform .5s ease,background .35s,border-color .35s}.nav.v{opacity:1;transform:translateY(0)}
.nl{display:flex;align-items:center;gap:10px;height:64px}.nl svg{width:24px;height:24px}.nl span{font-family:var(--fe);font-size:18px;letter-spacing:.4px;line-height:1}
.nm{display:flex;gap:24px;align-items:center;height:64px}.nm a{font-family:var(--fb);font-size:12px;font-weight:500;letter-spacing:.3px;opacity:.45;transition:opacity .2s;line-height:1}.nm a:hover{opacity:1}
.nr{display:flex;align-items:center;gap:14px;height:64px}
.ns{font-family:var(--fb);font-size:12px;font-weight:500;opacity:.45;transition:opacity .2s;line-height:1}.ns:hover{opacity:1}
.nc{font-family:var(--fb);font-size:12px;font-weight:600;padding:9px 20px;border-radius:var(--r);background:var(--dm);color:var(--cw);letter-spacing:.3px;transition:all .28s ease-out;display:inline-flex;align-items:center}.nc:hover{background:#3d4d42;transform:translateY(-1px)}
.tt{width:36px;height:20px;border-radius:10px;background:var(--card-b);position:relative;cursor:pointer;transition:background .3s;flex-shrink:0}.tt::after{content:'';position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:var(--sc);transition:transform .3s ease}[data-theme="dark"] .tt::after{transform:translateX(16px)}
.nt{display:none;flex-direction:column;gap:5px;width:22px;height:22px;justify-content:center;cursor:pointer}.nt span{display:block;height:1.5px;background:var(--fg);border-radius:1px;transition:.3s}
@media(max-width:768px){.nav{padding:0 16px;height:56px}.nm{display:none;position:absolute;top:56px;left:0;right:0;flex-direction:column;background:var(--bg);border-bottom:1px solid var(--card-b);padding:8px 0;gap:0}.nm.o{display:flex}.nm a{padding:12px 20px;font-size:13px}.nt{display:flex}.ns{display:none}}

/* HERO */
.hero{min-height:100svh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:80px 20px 60px}
.hd{width:44px;height:44px;margin-bottom:36px;opacity:0;transform:translateY(12px) scale(.9);transition:opacity .8s ease,transform .8s ease}.hd.i{opacity:1;transform:none}
.hero h1{font-family:var(--fe);font-size:clamp(40px,8.5vw,84px);font-weight:400;line-height:1.04;letter-spacing:-1.5px;opacity:0;transform:translateY(16px);transition:opacity .9s ease .12s,transform .9s ease .12s}.hero h1.i{opacity:1;transform:none}
.hs{font-size:clamp(14px,2.2vw,18px);font-weight:300;line-height:1.65;max-width:480px;letter-spacing:.15px;margin-top:16px;opacity:0;transform:translateY(10px);transition:opacity .7s ease .25s,transform .7s ease .25s}.hs.i{opacity:1;transform:none;color:var(--fg2)}
.ha{display:flex;gap:12px;margin-top:40px;opacity:0;transform:translateY(10px);transition:opacity .7s ease .4s,transform .7s ease .4s;flex-wrap:wrap;justify-content:center}.ha.i{opacity:1;transform:none}
.b1{font-family:var(--fb);font-size:14px;font-weight:600;padding:14px 30px;border-radius:var(--r);background:var(--dm);color:var(--cw);letter-spacing:.3px;transition:all .28s ease-out}.b1:hover{background:#3d4d42;transform:translateY(-2px);box-shadow:0 8px 28px rgba(51,64,54,.2)}
.b2{font-family:var(--fb);font-size:14px;font-weight:500;padding:14px 30px;border-radius:var(--r);border:1px solid var(--card-b);letter-spacing:.3px;transition:all .28s ease-out}.b2:hover{border-color:var(--fg);background:var(--card-h)}

/* SECTIONS */
.sec{padding:80px 20px;position:relative;transition:background .35s}.si{max-width:1080px;margin:0 auto}
.sl{font-family:var(--fb);font-size:10px;font-weight:600;letter-spacing:3px;text-transform:uppercase;color:var(--sc);margin-bottom:12px}
.st{font-family:var(--fe);font-size:clamp(30px,5.5vw,50px);font-weight:400;line-height:1.12;letter-spacing:-.5px;margin-bottom:16px}
.sd{font-size:15px;font-weight:300;line-height:1.7;max-width:520px;color:var(--fg2)}
.s2{background:var(--bg2);transition:background .35s}
.rv{opacity:0;transform:translateY(24px);transition:opacity .6s ease,transform .6s ease}.rv.vi{opacity:1;transform:none}
.r1{transition-delay:.06s}.r2{transition-delay:.12s}.r3{transition-delay:.18s}.r4{transition-delay:.24s}.r5{transition-delay:.3s}.r6{transition-delay:.36s}.r7{transition-delay:.42s}.r8{transition-delay:.48s}.r9{transition-delay:.54s}

/* INTRO */
.intro{text-align:center;padding:72px 20px;border-bottom:1px solid var(--card-b)}.iq{font-family:var(--fe);font-style:italic;font-size:clamp(20px,3.5vw,32px);line-height:1.45;max-width:600px;margin:0 auto;opacity:.65}.ip{font-size:14px;font-weight:300;line-height:1.75;max-width:560px;margin:24px auto 0;color:var(--fg2)}

/* ICONS */
.ico{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:16px;background:var(--card-h);transition:background .35s}.ico svg{width:20px;height:20px;stroke:var(--sc);stroke-width:1.5;fill:none;stroke-linecap:round;stroke-linejoin:round}

/* FEATURES */
.fg{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:44px}
.fc{padding:28px 24px;border-radius:var(--rl);background:var(--card);border:1px solid var(--card-b);transition:all .28s ease-out}.fc:hover{transform:translateY(-3px);box-shadow:0 12px 40px rgba(23,26,31,.06);border-color:rgba(181,110,69,.15)}
.fc h3{font-family:var(--fb);font-size:15px;font-weight:600;margin-bottom:8px;letter-spacing:.15px}.fc p{font-size:13px;line-height:1.6;color:var(--fg2);font-weight:300}
@media(max-width:768px){.fg{grid-template-columns:1fr}}@media(min-width:769px) and (max-width:1024px){.fg{grid-template-columns:repeat(2,1fr)}}

/* CAPABILITIES */
.cg{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:44px}
.cc{display:flex;gap:16px;padding:24px 22px;border-radius:var(--rl);border:1px solid var(--card-b);background:var(--card);transition:all .28s ease-out}.cc:hover{border-color:rgba(181,110,69,.15);background:var(--card-h)}
.cn{font-family:var(--fe);font-size:28px;color:var(--glow);opacity:.5;flex-shrink:0;width:32px;line-height:1}.cc h3{font-family:var(--fb);font-size:14px;font-weight:600;margin-bottom:6px}.cc p{font-size:12px;line-height:1.6;color:var(--fg2)}
@media(max-width:768px){.cg{grid-template-columns:1fr}}

/* MARQUEE */
.mq{padding:28px 0;overflow:hidden;border-top:1px solid var(--card-b);border-bottom:1px solid var(--card-b)}.mt{display:flex;gap:36px;animation:mqa 26s linear infinite;white-space:nowrap}.mi{font-family:var(--fb);font-size:12px;font-weight:500;letter-spacing:2px;text-transform:uppercase;opacity:.15;flex-shrink:0}.mdt{width:4px;height:4px;border-radius:50%;background:var(--sc);opacity:.25;flex-shrink:0;align-self:center}@keyframes mqa{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}

/* 9 MODULES */
.mg9{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:44px}
.mo{padding:28px 24px;border-radius:var(--rl);background:var(--card);border:1px solid var(--card-b);transition:all .28s ease-out}.mo:hover{transform:translateY(-3px);border-color:rgba(181,110,69,.15);box-shadow:0 12px 40px rgba(23,26,31,.06)}
.mo-pre{font-family:var(--fb);font-size:9px;font-weight:600;letter-spacing:2.5px;text-transform:uppercase;color:var(--sc);margin-bottom:4px;opacity:.7}
.mo h3{font-family:var(--fe);font-size:22px;margin-bottom:8px}.mo p{font-size:12px;line-height:1.6;color:var(--fg2)}
@media(max-width:768px){.mg9{grid-template-columns:1fr}}@media(min-width:769px) and (max-width:1024px){.mg9{grid-template-columns:repeat(2,1fr)}}

/* TRUST */
.tg{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin-top:44px;text-align:center}.tn{font-family:var(--fe);font-size:clamp(32px,4.5vw,48px);font-weight:400;color:var(--sc);line-height:1}.tl{font-family:var(--fb);font-size:11px;font-weight:500;letter-spacing:1px;text-transform:uppercase;opacity:.3;margin-top:6px}@media(max-width:600px){.tg{grid-template-columns:repeat(2,1fr);gap:32px 16px}}

/* CTA */
.cs{text-align:center}.cb{display:inline-flex;align-items:center;gap:8px;font-family:var(--fb);font-size:11px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;padding:8px 20px;border-radius:20px;background:rgba(143,163,155,.12);color:var(--sage);margin-bottom:28px}.cd{width:7px;height:7px;border-radius:50%;background:var(--sage);animation:pd 2s ease infinite}@keyframes pd{0%,100%{opacity:1}50%{opacity:.3}}.cs .st{max-width:520px;margin:0 auto 16px}.cs .sd{max-width:420px;margin:0 auto 40px;text-align:center}

/* FOOTER */
.ft{padding:56px 20px 36px;background:#111316;color:var(--sm)}.ftp{max-width:1080px;margin:0 auto;display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:40px}.flg{display:flex;align-items:center;gap:10px;margin-bottom:12px}.flg svg{width:20px;height:20px}.flg span{font-family:var(--fe);font-size:16px}.ftg{font-size:12px;opacity:.3;font-weight:300;line-height:1.6;max-width:240px}.fco h4{font-family:var(--fb);font-size:10px;font-weight:600;letter-spacing:2px;text-transform:uppercase;opacity:.25;margin-bottom:14px}.fco a{display:block;font-size:12px;opacity:.4;transition:opacity .2s;margin-bottom:8px;font-weight:300}.fco a:hover{opacity:.8}.fbt{max-width:1080px;margin:40px auto 0;padding-top:20px;border-top:1px solid rgba(234,229,222,.05);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}.fcp{font-size:11px;opacity:.2;font-weight:300}.fen{font-family:var(--fe);font-style:italic;font-size:12px;opacity:.15}
@media(max-width:768px){.ftp{grid-template-columns:1fr 1fr;gap:28px}.fbt{flex-direction:column;text-align:center}}@media(max-width:480px){.ftp{grid-template-columns:1fr}}
/* CHANNELS */
.ch-sec{padding:80px 20px;text-align:center;position:relative;overflow:hidden}
.ch-sec .si{position:relative;z-index:1}
.ch-grid{display:flex;flex-wrap:wrap;justify-content:center;gap:36px 52px;margin-top:48px;margin-bottom:32px}
.ch-name{font-size:clamp(14px,1.8vw,17px);font-weight:400;opacity:.12;transition:opacity .4s;letter-spacing:.3px;color:var(--fg)}
.ch-name:hover{opacity:.55}
/* brand-specific typography for channel names */
.ch-airbnb{font-family:'Cereal','Manrope',sans-serif;font-weight:700;text-transform:lowercase}
.ch-booking{font-family:var(--fb);font-weight:700}
.ch-expedia{font-family:var(--fb);font-weight:600}
.ch-vrbo{font-family:var(--fb);font-weight:800;letter-spacing:4px;text-transform:uppercase;font-size:clamp(14px,1.8vw,17px)}
.ch-agoda{font-family:var(--fb);font-weight:600;text-transform:lowercase}
.ch-trip{font-family:var(--fb);font-weight:500}
.ch-traveloka{font-family:var(--fb);font-weight:500;text-transform:lowercase}
.ch-rakuten{font-family:var(--fe);font-weight:400;font-style:italic}
.ch-despegar{font-family:var(--fb);font-weight:500;text-transform:lowercase}
.ch-klook{font-family:var(--fb);font-weight:800;letter-spacing:1px}
.ch-makemytrip{font-family:var(--fb);font-weight:500}
.ch-google{font-family:var(--fi);font-weight:300;font-size:clamp(12px,1.5vw,14px)}
.ch-hostelworld{font-family:var(--fb);font-weight:600;text-transform:lowercase}
.ch-hotelbeds{font-family:var(--fb);font-weight:700}
.ch-note{font-size:11px;color:var(--fg2);opacity:.3;max-width:640px;margin:0 auto;font-weight:300;font-style:italic}

/* ARCHITECTURAL PATTERN BG */
.arch-bg{position:absolute;inset:0;overflow:hidden;pointer-events:none}
.arch-bg svg{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:140%;height:140%;opacity:.025}
[data-theme="dark"] .arch-bg svg{opacity:.03}

/* PRICING */
.pr-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;margin-top:44px;max-width:800px;margin-left:auto;margin-right:auto}
.pr-card{padding:36px 28px;border-radius:var(--rl);background:var(--card);border:1px solid var(--card-b);transition:all .28s ease-out;display:flex;flex-direction:column}
.pr-card:hover{border-color:rgba(181,110,69,.2);transform:translateY(-3px);box-shadow:0 12px 40px rgba(23,26,31,.06)}
.pr-card.feat{border-color:rgba(181,110,69,.2)}
.pr-tag{font-family:var(--fb);font-size:9px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--sc);margin-bottom:6px;opacity:.7}
.pr-card h3{font-family:var(--fe);font-size:26px;margin-bottom:4px}
.pr-sub{font-size:13px;color:var(--fg2);margin-bottom:20px;font-weight:300}
.pr-price{font-family:var(--fe);font-size:20px;color:var(--sc);margin-bottom:20px}
.pr-list{list-style:none;flex:1;margin-bottom:24px}
.pr-list li{font-size:13px;line-height:1.6;color:var(--fg2);font-weight:300;padding:8px 0;border-bottom:1px solid var(--card-b);display:flex;align-items:flex-start;gap:10px}
.pr-list li svg{width:16px;height:16px;stroke:var(--sage);stroke-width:2;fill:none;flex-shrink:0;margin-top:2px}
.pr-btn{font-family:var(--fb);font-size:13px;font-weight:600;padding:13px 28px;border-radius:var(--r);text-align:center;letter-spacing:.3px;transition:all .28s ease-out;display:block}
.pr-btn-p{background:var(--dm);color:var(--cw)}.pr-btn-p:hover{background:#3d4d42;transform:translateY(-1px)}
.pr-btn-s{border:1px solid var(--card-b)}.pr-btn-s:hover{border-color:var(--fg);background:var(--card-h)}
@media(max-width:768px){.pr-grid{grid-template-columns:1fr;max-width:400px}}

/* FAQ */
.faq{margin-top:56px;max-width:720px;margin-left:auto;margin-right:auto}
.fq{border-bottom:1px solid var(--card-b);padding:24px 0}
.fq h3{font-family:var(--fb);font-size:15px;font-weight:600;margin-bottom:8px;cursor:pointer;display:flex;align-items:center;justify-content:space-between}
.fq h3::after{content:'+';font-family:var(--fi);font-weight:300;font-size:20px;opacity:.3;transition:transform .28s}
.fq.open h3::after{transform:rotate(45deg)}
.fq p{font-size:14px;line-height:1.7;color:var(--fg2);font-weight:300;max-height:0;overflow:hidden;transition:max-height .35s ease,opacity .35s ease;opacity:0}
.fq.open p{max-height:200px;opacity:1}

@media(prefers-reduced-motion:reduce){.domaniqo-landing *,.domaniqo-landing *::before,.domaniqo-landing *::after{animation-duration:.01ms!important;transition-duration:.01ms!important}.mt{animation:none}}`;

const HTML_CONTENT = `<div class="domaniqo-landing" data-theme="dark"><!-- SPLASH -->
<div id="sp"><div class="gr" id="sgr"></div>
<div id="sw" style="display:flex;flex-direction:column;align-items:center;position:relative">
<div id="smw" style="opacity:0;transition:opacity .7s ease"><div id="smr" style="transform:rotate(-90deg);transition:none;transform-origin:center center">
<svg id="ss" width="160" height="160" viewBox="0 0 64 64" fill="none" style="overflow:visible">
<defs><filter id="wg" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="1.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter><filter id="dg" x="-150%" y="-150%" width="400%" height="400%"><feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter><filter id="fg" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
<path id="xo" d="M16 6H28C46 6 58 18 58 32C58 46 46 58 28 58H16Z" stroke="#B56E45" stroke-width="2.2" stroke-linejoin="round" fill="none" opacity=".3"/><line id="xv" x1="28" y1="6" x2="28" y2="58" stroke="#B56E45" stroke-width="1.2" opacity=".2"/><line id="xh" x1="16" y1="32" x2="52" y2="32" stroke="#B56E45" stroke-width="1.2" opacity=".2"/><path id="xa" d="M28 13C40 13 51 22 51 32C51 42 40 51 28 51" stroke="#B56E45" stroke-width="1.08" fill="none" opacity=".15"/>
<g id="trc"></g><g id="fgl"></g>
<line id="wv" x1="38" y1="18" x2="38" y2="46" stroke="#B56E45" stroke-width=".7" opacity="0"/><line id="wh" x1="30" y1="32" x2="46" y2="32" stroke="#B56E45" stroke-width=".7" opacity="0"/>
</svg></div></div>
<div id="snm" style="margin-top:32px;text-align:center;opacity:0;transform:translateY(16px) scale(.97);transition:all 1.1s cubic-bezier(.25,.1,.25,1)"><span style="font-family:'Instrument Serif',Georgia,serif;font-size:40px;color:#EAE5DE;letter-spacing:1.2px">Domaniqo</span></div>
<div id="sdv" style="width:0;height:1px;background:#B56E45;margin:12px auto;opacity:0;transition:all .8s ease .4s"></div>
<div id="stg" style="text-align:center;opacity:0;transform:translateY(8px);transition:all .9s ease .5s"><span style="font-family:'Instrument Serif',Georgia,serif;font-size:15px;font-style:italic;color:#D6C8B7;opacity:.7">See every stay.</span></div>
<div id="ssp" style="margin-top:28px;text-align:center;font-size:8px;letter-spacing:3.5px;color:#B5AFA6;font-family:Manrope,sans-serif;font-weight:500;opacity:0;transition:opacity .7s ease .9s">CALM COMMAND FOR MODERN HOSPITALITY</div>
</div></div>

<!-- NAV -->
<nav class="nav" id="nav">
<a href="/" class="nl"><svg viewBox="0 0 64 64" fill="none"><path d="M16 6H28C46 6 58 18 58 32C58 46 46 58 28 58H16Z" stroke="#B56E45" stroke-width="2.2" stroke-linejoin="round" fill="none"/><line x1="28" y1="6" x2="28" y2="58" stroke="#B56E45" stroke-width="1.2"/><line x1="16" y1="32" x2="52" y2="32" stroke="#B56E45" stroke-width="1.2"/><path d="M28 13C40 13 51 22 51 32C51 42 40 51 28 51" stroke="#B56E45" stroke-width="1.08" fill="none"/></svg><span>Domaniqo</span></a>
<div class="nm" id="nmid"><a href="/platform">Platform</a><a href="/channels">Channels</a><a href="/pricing">Pricing</a><a href="/about">About</a></div>
<div class="nr"><a href="/login" class="ns">Sign in</a><div class="tt" id="themeToggle" title="Toggle theme"></div><a href="/get-started" class="nc">Get Started</a></div>
<div class="nt" onclick="document.getElementById('nmid').classList.toggle('o')"><span></span><span></span><span></span></div>
</nav>

<!-- HERO -->
<section class="hero" style="position:relative;overflow:hidden">
<div class="arch-bg"><svg viewBox="0 0 800 600" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="150" y="80" width="300" height="260" stroke="currentColor" stroke-width=".4" transform="rotate(8 300 210)"/>
<rect x="380" y="200" width="260" height="220" stroke="currentColor" stroke-width=".4" transform="rotate(-12 510 310)"/>
<rect x="60" y="320" width="180" height="180" stroke="currentColor" stroke-width=".4" transform="rotate(4 150 410)"/>
</svg></div>
<svg class="hd" id="hd" viewBox="0 0 64 64" fill="none"><path d="M16 6H28C46 6 58 18 58 32C58 46 46 58 28 58H16Z" stroke="#B56E45" stroke-width="2.2" stroke-linejoin="round" fill="none"/><line x1="28" y1="6" x2="28" y2="58" stroke="#B56E45" stroke-width="1.2"/><line x1="16" y1="32" x2="52" y2="32" stroke="#B56E45" stroke-width="1.2"/><path d="M28 13C40 13 51 22 51 32C51 42 40 51 28 51" stroke="#B56E45" stroke-width="1.08" fill="none"/></svg>
<h1 id="hh">See every stay.</h1>
<p class="hs" id="hsu">The deep operations platform for modern hospitality. Calm command across operations, teams, finance, and guest experience.</p>
<div class="ha" id="hac"><a href="/get-started" class="b1">Onboard Your Property</a><a href="/login" class="b2">Sign in →</a></div>
</section>

<!-- INTRO -->
<div class="intro rv"><p class="iq">Hospitality is people.<br>Operations should disappear.</p><p class="ip">Property managers juggle bookings across OTAs, coordinate field teams, reconcile finances, and keep guests happy — often from scattered tools. Domaniqo brings it all under one calm surface.</p></div>

<!-- PLATFORM -->
<section class="sec s2"><div class="si">
<div class="sl rv">The Platform</div><div class="st rv r1">One system. Every surface.</div>
<div class="fg">
<div class="fc rv r1"><div class="ico"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="9" y1="4" x2="9" y2="10"/></svg></div><h3>Booking Intelligence</h3><p>Booking records from every source — normalized, conflict-checked, and audit-trailed in one timeline.</p></div>
<div class="fc rv r2"><div class="ico"><svg viewBox="0 0 24 24"><path d="M9 11l3 3 8-8"/><rect x="3" y="3" width="18" height="18" rx="2"/></svg></div><h3>Task Engine</h3><p>Auto-generated tasks from bookings, SLA tracking, escalation, and field-team mobile surfaces.</p></div>
<div class="fc rv r3"><div class="ico"><svg viewBox="0 0 24 24"><line x1="12" y1="2" x2="12" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg></div><h3>Financial Clarity</h3><p>Revenue aggregation, owner statements, cashflow projection, and multi-currency reconciliation.</p></div>
<div class="fc rv r4"><div class="ico"><svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M6 21v-2a4 4 0 014-4h4a4 4 0 014 4v2"/></svg></div><h3>Guest Experience</h3><p>Stay history, preference tracking, QR-based access portals, and connected communication channels.</p></div>
<div class="fc rv r5"><div class="ico"><svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg></div><h3>Operational Shell</h3><p>Adaptive layout — desktop command center, tablet review, mobile field action. One platform, every device.</p></div>
<div class="fc rv r6"><div class="ico"><svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg></div><h3>Connected Notifications</h3><p>LINE, WhatsApp, Telegram. Instant task alerts to the right person at the right time.</p></div>
</div></div></section>

<!-- CAPABILITIES -->
<section class="sec"><div class="si">
<div class="sl rv">Capabilities</div><div class="st rv r1">Built deep, not wide.</div>
<div class="cg">
<div class="cc rv r1"><div class="cn">01</div><div><h3>Booking Normalizer</h3><p>Bookings from any source — Airbnb, Booking.com, Agoda, iCal — normalized into one canonical format.</p></div></div>
<div class="cc rv r2"><div class="cn">02</div><div><h3>Event-Sourced Booking Core</h3><p>Append-only events, idempotent ingestion, conflict detection, full audit trail.</p></div></div>
<div class="cc rv r3"><div class="cn">03</div><div><h3>SLA Escalation Engine</h3><p>5-minute critical ack window, timer-based escalation, deterministic state guards.</p></div></div>
<div class="cc rv r4"><div class="cn">04</div><div><h3>Owner Financial Layer</h3><p>Per-property revenue, management fees, payout timelines, PDF statements.</p></div></div>
<div class="cc rv r5"><div class="cn">05</div><div><h3>Portfolio Intelligence</h3><p>Cross-property dashboards, anomaly detection, morning briefings, AI copilot.</p></div></div>
<div class="cc rv r6"><div class="cn">06</div><div><h3>Calendar Sync Layer</h3><p>Calendar feed ingestion via iCal and URL import, conflict detection, sync health monitoring.</p></div></div>
</div></div></section>

<!-- MARQUEE -->
<div class="mq"><div class="mt"><span class="mi">Nothing hidden</span><span class="mdt"></span><span class="mi">Operations, resolved</span><span class="mdt"></span><span class="mi">Know before it breaks</span><span class="mdt"></span><span class="mi">No blind spots</span><span class="mdt"></span><span class="mi">Deep ops · Clean surface</span><span class="mdt"></span><span class="mi">Run every stay with clarity</span><span class="mdt"></span><span class="mi">Nothing hidden</span><span class="mdt"></span><span class="mi">Operations, resolved</span><span class="mdt"></span><span class="mi">Know before it breaks</span><span class="mdt"></span><span class="mi">No blind spots</span><span class="mdt"></span><span class="mi">Deep ops · Clean surface</span><span class="mdt"></span><span class="mi">Run every stay with clarity</span><span class="mdt"></span></div></div>

<!-- CHANNELS -->
<section class="ch-sec sec">
<div class="arch-bg"><svg viewBox="0 0 800 600" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="120" y="60" width="320" height="280" stroke="currentColor" stroke-width=".5" transform="rotate(12 280 200)"/>
<rect x="350" y="180" width="280" height="240" stroke="currentColor" stroke-width=".5" transform="rotate(-8 490 300)"/>
<rect x="80" y="280" width="200" height="200" stroke="currentColor" stroke-width=".5" transform="rotate(5 180 380)"/>
<rect x="500" y="40" width="220" height="320" stroke="currentColor" stroke-width=".5" transform="rotate(-15 610 200)"/>
<line x1="0" y1="300" x2="800" y2="300" stroke="currentColor" stroke-width=".3" opacity=".5"/>
<line x1="400" y1="0" x2="400" y2="600" stroke="currentColor" stroke-width=".3" opacity=".5"/>
</svg></div>
<div class="si">
<div class="sl rv">Connected Channels</div>
<p class="sd rv r1" style="text-align:center;margin:0 auto;opacity:.40;max-width:520px">Domaniqo syncs with the booking platforms your operations depend on.</p>
<div class="ch-grid">
<span class="ch-name ch-airbnb rv r1">airbnb</span>
<span class="ch-name ch-booking rv r2">Booking.com</span>
<span class="ch-name ch-expedia rv r3">Expedia</span>
<span class="ch-name ch-vrbo rv r4">VRBO</span>
<span class="ch-name ch-agoda rv r5">agoda</span>
<span class="ch-name ch-traveloka rv r6">traveloka</span>
<span class="ch-name ch-trip rv r7">Trip.com</span>
<span class="ch-name ch-rakuten rv r8">Rakuten</span>
<span class="ch-name ch-despegar rv r9">despegar</span>
<span class="ch-name ch-klook rv r1">Klook</span>
<span class="ch-name ch-makemytrip rv r2">MakeMyTrip</span>
<span class="ch-name ch-google rv r3">Google Vacation Rentals</span>
<span class="ch-name ch-hostelworld rv r4">Hostelworld</span>
<span class="ch-name ch-hotelbeds rv r5">HotelBeds</span>
</div>
<p class="ch-note rv r6">Domaniqo operates as an independent platform that integrates with these booking channels. Channel names and trademarks belong to their respective owners.</p>
</div>
</section>

<!-- 9 MODULES -->
<section class="sec s2"><div class="si">
<div class="sl rv">The System</div><div class="st rv r1">Eight modules. One platform.</div>
<p class="sd rv r2">Each module handles a distinct domain. Together, they form a complete operating layer.</p>
<div class="mg9">
<div class="mo rv r1"><div class="ico"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v4m0 12v4m-10-10h4m12 0h4"/><path d="M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83m0-14.14l-2.83 2.83m-8.48 8.48l-2.83 2.83"/></svg></div><div class="mo-pre">Domaniqo</div><h3>Core</h3><p>The foundation. Property data, configuration, booking records, and the canonical truth layer.</p></div>
<div class="mo rv r2"><div class="ico"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="9" y1="4" x2="9" y2="10"/></svg></div><div class="mo-pre">Domaniqo</div><h3>Stays</h3><p>Reservation lifecycle. Multi-source imports, normalization, conflict detection, guest-stay continuity.</p></div>
<div class="mo rv r3"><div class="ico"><svg viewBox="0 0 24 24"><path d="M9 11l3 3 8-8"/><rect x="3" y="3" width="18" height="18" rx="2"/></svg></div><div class="mo-pre">Domaniqo</div><h3>Ops</h3><p>Task orchestration. Cleaning, maintenance, prep — tracked with SLA enforcement and escalation.</p></div>
<div class="mo rv r4"><div class="ico"><svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M6 21v-2a4 4 0 014-4h4a4 4 0 014 4v2"/></svg></div><div class="mo-pre">Domaniqo</div><h3>Guests</h3><p>Guest profiles, check-in flows, welcome sequences, feedback, pre-arrival workflows.</p></div>
<div class="mo rv r5"><div class="ico"><svg viewBox="0 0 24 24"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg></div><div class="mo-pre">Domaniqo</div><h3>Inbox</h3><p>Unified messaging across LINE, WhatsApp, Telegram, SMS, email — one operational thread.</p></div>
<div class="mo rv r6"><div class="ico"><svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg></div><div class="mo-pre">Domaniqo</div><h3>Teams</h3><p>Roles, permissions, assignments, accountability, escalation paths, availability scheduling.</p></div>
<div class="mo rv r7"><div class="ico"><svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg></div><div class="mo-pre">Domaniqo</div><h3>Pulse</h3><p>Real-time operational intelligence. Anomaly detection, health monitoring, dashboards, morning briefings.</p></div>
<div class="mo rv r8"><div class="ico"><svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div><div class="mo-pre">Domaniqo</div><h3>Standards</h3><p>Readiness scores, checklists, before/after photos, quality assurance across every property.</p></div>
</div></div></section>

<!-- TRUST -->
<section class="sec"><div class="si">
<div class="sl rv">Trust</div><div class="st rv r1">Quiet confidence, earned.</div>
<div class="tg">
<div class="rv r1"><div class="tn">8,000+</div><div class="tl">Contract Tests</div></div>
<div class="rv r2"><div class="tn">14+</div><div class="tl">Booking Sources</div></div>
<div class="rv r3"><div class="tn">865</div><div class="tl">Development Phases</div></div>
<div class="rv r4"><div class="tn">3+</div><div class="tl">Languages</div></div>
</div></div></section>

<!-- PRICING -->
<section class="sec s2"><div class="si">
<div class="sl rv" style="text-align:center">Investment</div>
<div class="st rv r1" style="text-align:center;max-width:600px;margin:0 auto 8px">Clarity has a price.<br>Chaos costs more.</div>
<p class="sd rv r2" style="text-align:center;max-width:460px;margin:0 auto">Two paths. No hidden fees. No per-channel charges.</p>
<div class="pr-grid">
<div class="pr-card rv r3">
<div class="pr-tag">For property managers</div>
<h3>Platform</h3>
<p class="pr-sub">You manage operations. You set the price for your clients.</p>
<div class="pr-price">Monthly subscription</div>
<ul class="pr-list">
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Full platform access — all 8 modules</li>
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Booking import from 14+ sources</li>
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Unlimited properties</li>
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Multi-channel notifications</li>
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Team management &amp; roles</li>
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Financial dashboards &amp; owner reports</li>
</ul>
<a href="/get-started" class="pr-btn pr-btn-s">Get in Touch</a>
</div>
<div class="pr-card feat rv r4">
<div class="pr-tag">For property owners</div>
<h3>Managed</h3>
<p class="pr-sub">We handle everything. You pay only when you earn.</p>
<div class="pr-price">Per booking only</div>
<ul class="pr-list">
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>No monthly fee — pay per booking</li>
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Full cleaning, check-in &amp; check-out</li>
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Maintenance &amp; property care</li>
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Guest communication &amp; support</li>
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Financial reporting &amp; transparency</li>
<li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Quality standards &amp; readiness</li>
</ul>
<a href="/get-started" class="pr-btn pr-btn-p">Book a Demo</a>
</div>
</div>

<div class="faq">
<div class="sl rv" style="text-align:center;margin-top:56px">Questions</div>
<div class="st rv r1" style="text-align:center;max-width:600px;margin:0 auto 16px;font-size:clamp(24px,4vw,36px)">Common questions, honest answers.</div>

<div class="fq rv r2"><h3>Is there a free trial?</h3><p>Yes. Starting next month — full platform access, no credit card required.</p></div>
<div class="fq rv r3"><h3>How does pricing work?</h3><p>Two paths. Property managers pay a monthly subscription. Individual property owners pay per booking only — no monthly fee. You pay when you earn.</p></div>
<div class="fq rv r4"><h3>Do you charge per channel?</h3><p>No. All sources, all channels, all properties included. No hidden fees.</p></div>
<div class="fq rv r5"><h3>What if I need a channel you don't support?</h3><p>We add sources based on demand and are moving to direct API integrations soon. For Platform subscribers, we build custom connections for your specific needs.</p></div>
<div class="fq rv r6"><h3>Can I switch between plans?</h3><p>Yes. You can move between the Platform and Managed paths as your business evolves. No lock-in.</p></div>
<div class="fq rv r7"><h3>What currencies do you support?</h3><p>All major currencies, natively. Exchange rate tracking included.</p></div>
</div>
</div></section>

<!-- CTA -->
<section class="sec s2 cs"><div class="si">
<div class="cb rv"><span class="cd"></span> In active development</div>
<div class="st rv r1">Ready to see every stay?</div>
<p class="sd rv r2" style="text-align:center">Domaniqo is in active development. Early access is available for select operators.</p>
<div class="rv r3" style="text-align:center"><a href="/get-started" class="b1">Book a Demo</a></div>
<p class="rv r4" style="text-align:center;margin-top:16px;font-size:12px;opacity:.45"><a href="mailto:info@domaniqo.com" style="color:var(--sc)">info@domaniqo.com</a></p>
</div></section>

<!-- FOOTER -->
<footer class="ft"><div class="ftp">
<div><div class="flg"><svg viewBox="0 0 64 64" fill="none" width="20" height="20"><path d="M16 6H28C46 6 58 18 58 32C58 46 46 58 28 58H16Z" stroke="#B56E45" stroke-width="2.2" stroke-linejoin="round" fill="none"/><line x1="28" y1="6" x2="28" y2="58" stroke="#B56E45" stroke-width="1.2"/><line x1="16" y1="32" x2="52" y2="32" stroke="#B56E45" stroke-width="1.2"/><path d="M28 13C40 13 51 22 51 32C51 42 40 51 28 51" stroke="#B56E45" stroke-width="1.08" fill="none"/></svg><span>Domaniqo</span></div><p class="ftg">The deep operations platform for modern hospitality.</p></div>
<div class="fco"><h4>Product</h4><a href="/platform">Platform</a><a href="/channels">Channels</a><a href="/inbox">Inbox</a><a href="/reviews">Reviews</a></div>
<div class="fco"><h4>Company</h4><a href="/about">About</a><a href="/pricing">Pricing</a><a href="/early-access">Early Access</a></div>
<div class="fco"><h4>Legal</h4><a href="/privacy">Privacy Policy</a><a href="/terms">Terms of Use</a><a href="mailto:info@domaniqo.com">Contact</a></div>
</div><div class="fbt"><div class="fcp">© 2026 Domaniqo. All rights reserved.</div><div class="fen">Calm command for modern hospitality.</div></div></footer></div>`;

const SCRIPT_CONTENT = `(function(){
var $=function(s){return document.getElementById(s)};
var tt=$('themeToggle'),h=document.querySelector('.domaniqo-landing');
var sv=localStorage.getItem('domaniqo-theme');
if(sv)h.setAttribute('data-theme',sv);
tt.addEventListener('click',function(){var c=h.getAttribute('data-theme'),n=c==='dark'?'light':'dark';h.setAttribute('data-theme',n);localStorage.setItem('domaniqo-theme',n);document.querySelector('meta[name="theme-color"]').content=n==='dark'?'#171A1F':'#F8F6F2'});
var sp=$('sp'),mw=$('smw'),mr=$('smr'),wv=$('wv'),wh=$('wh'),trc=$('trc'),fgl=$('fgl'),xo=$('xo'),xv=$('xv'),xh=$('xh'),xa=$('xa'),sgr=$('sgr');
var lc='#D4956A',lb='#DBA57A';
function ns(t,a){var e=document.createElementNS('http://www.w3.org/2000/svg',t);for(var k in a)e.setAttribute(k,a[k]);return e}
setTimeout(function(){mw.style.opacity='1'},150);
setTimeout(function(){wv.setAttribute('opacity','0.55');wh.setAttribute('opacity','0.55')},900);
setTimeout(function(){wv.style.transition='opacity .5s ease';wh.style.transition='opacity .5s ease .05s';wv.setAttribute('opacity','0');wh.setAttribute('opacity','0');mr.style.transition='transform 1.4s cubic-bezier(.22,.61,.36,1)';mr.style.transform='rotate(0deg)';trc.innerHTML='';trc.appendChild(ns('path',{d:'M16 6H28C46 6 58 18 58 32C58 46 46 58 28 58H16Z',stroke:lc,'stroke-width':'2.4','stroke-linejoin':'round',fill:'none',filter:'url(#wg)','stroke-dasharray':'200',style:'animation:to .9s ease forwards'}));trc.appendChild(ns('line',{x1:'28',y1:'6',x2:'28',y2:'58',stroke:lc,'stroke-width':'1.4',filter:'url(#wg)','stroke-dasharray':'52',style:'animation:tv .4s ease .3s forwards'}));trc.appendChild(ns('line',{x1:'16',y1:'32',x2:'52',y2:'32',stroke:lc,'stroke-width':'1.4',filter:'url(#wg)','stroke-dasharray':'36',style:'animation:th .35s ease .45s forwards'}));trc.appendChild(ns('path',{d:'M28 13C40 13 51 22 51 32C51 42 40 51 28 51',stroke:lc,'stroke-width':'1.3',fill:'none',filter:'url(#wg)','stroke-dasharray':'80',style:'animation:ta .5s ease .55s forwards'}));trc.appendChild(ns('circle',{r:'1.8',fill:lb,filter:'url(#dg)',style:"offset-path:path('M16 6 L28 6 C46 6 58 18 58 32 C58 46 46 58 28 58 L16 58 L16 6');animation:dr .9s ease forwards"}));trc.appendChild(ns('circle',{r:'1.5',fill:lb,filter:'url(#dg)',style:"offset-path:path('M28 13C40 13 51 22 51 32C51 42 40 51 28 51');animation:da .6s ease .55s forwards"}))},2700);
setTimeout(function(){xo.setAttribute('opacity','1');xo.style.transition='opacity .5s ease';xv.setAttribute('opacity','1');xv.style.transition='opacity .5s ease';xh.setAttribute('opacity','1');xh.style.transition='opacity .5s ease';xa.setAttribute('opacity','1');xa.style.transition='opacity .5s ease';mr.style.animation='sg 1s ease forwards';fgl.innerHTML='';fgl.appendChild(ns('path',{d:'M16 6H28C46 6 58 18 58 32C58 46 46 58 28 58H16Z',stroke:lc,'stroke-width':'3.5','stroke-linejoin':'round',fill:'none',filter:'url(#fg)',style:'animation:gf 1.2s ease forwards'}))},4200);
setTimeout(function(){$('snm').style.opacity='1';$('snm').style.transform='translateY(0) scale(1)';$('sdv').style.width='36px';$('sdv').style.opacity='.4';$('stg').style.opacity='1';$('stg').style.transform='translateY(0)';$('ssp').style.opacity='.25'},5200);
setTimeout(function(){$('snm').style.transition='opacity .4s';$('snm').style.opacity='0';$('sdv').style.transition='opacity .3s';$('sdv').style.opacity='0';$('stg').style.transition='opacity .3s';$('stg').style.opacity='0';$('ssp').style.transition='opacity .3s';$('ssp').style.opacity='0';sgr.style.transition='opacity .5s';sgr.style.opacity='0';sp.style.transition='background .6s ease';sp.style.background='transparent';sp.classList.add('m');var hd=$('hd'),hr=hd.getBoundingClientRect(),sr=$('ss').getBoundingClientRect();var dx=(hr.left+hr.width/2)-(sr.left+sr.width/2),dy=(hr.top+hr.height/2)-(sr.top+sr.height/2),sc=hr.width/sr.width;$('ss').style.transition='all .7s cubic-bezier(.25,.1,.25,1)';$('ss').style.transform='translate('+dx+'px,'+dy+'px) scale('+sc+')';$('ss').style.opacity='0';setTimeout(function(){sp.classList.add('g');hd.classList.add('i');$('hh').classList.add('i');$('hsu').classList.add('i');$('hac').classList.add('i');$('nav').classList.add('v')},700)},6400);
var obs=new IntersectionObserver(function(e){e.forEach(function(x){if(x.isIntersecting)x.target.classList.add('vi')})},{threshold:.12});document.querySelectorAll('.rv').forEach(function(el){obs.observe(el)});
// FAQ toggles
document.querySelectorAll('.fq h3').forEach(function(h){h.addEventListener('click',function(){var p=this.parentElement;p.classList.toggle('open')})});
})();`;

export default function LandingPage() {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    // Restore theme on the scoped container (not document root)
    const wrapper = document.querySelector('.domaniqo-landing');
    const sv = localStorage.getItem('domaniqo-theme');
    if (sv && wrapper) wrapper.setAttribute('data-theme', sv);

    // Run the landing page interactive logic via string execution
    // (bypasses TypeScript checking on vanilla JS animation code)
    const timer = setTimeout(() => {
      try {
        // eslint-disable-next-line no-new-func
        new Function(SCRIPT_CONTENT)();
      } catch(e) {
        console.warn('Landing script error:', e);
      }
    }, 80);
    return () => clearTimeout(timer);
  }, []);

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: CSS_CONTENT }} />
      <div dangerouslySetInnerHTML={{ __html: HTML_CONTENT }} />
    </>
  );
}
