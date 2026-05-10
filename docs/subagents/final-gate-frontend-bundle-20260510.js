(function(){const o=document.createElement("link").relList;if(o&&o.supports&&o.supports("modulepreload"))return;for(const n of document.querySelectorAll('link[rel="modulepreload"]'))i(n);new MutationObserver(n=>{for(const d of n)if(d.type==="childList")for(const l of d.addedNodes)l.tagName==="LINK"&&l.rel==="modulepreload"&&i(l)}).observe(document,{childList:!0,subtree:!0});function a(n){const d={};return n.integrity&&(d.integrity=n.integrity),n.referrerPolicy&&(d.referrerPolicy=n.referrerPolicy),n.crossOrigin==="use-credentials"?d.credentials="include":n.crossOrigin==="anonymous"?d.credentials="omit":d.credentials="same-origin",d}function i(n){if(n.ep)return;n.ep=!0;const d=a(n);fetch(n.href,d)}})();class $ extends Error{status;code;requestId;jobId;constructor(o,a={}){super(o),this.name="ApiError",this.status=a.status,this.code=a.code,this.requestId=a.requestId,this.jobId=a.jobId}}const W=e=>e.replace(/\/+$/,""),u=e=>{const o=e.trim();return W(o||"http://localhost:8080")},G=(e,o,a)=>{if(o)return new URL(o,`${u(e)}/`).toString();if(a){const i=a.split("/").filter(Boolean).pop();if(i)return`${u(e)}/audio/${encodeURIComponent(i)}`}return""},m=(e,o,a,i="artifacts")=>{if(o)return new URL(o,`${u(e)}/`).toString();if(a){const n=a.split("/").filter(Boolean).pop();if(n)return`${u(e)}/${i}/${encodeURIComponent(n)}`}return""},K=async e=>{const o=e.headers.get("X-Request-ID")??void 0,a=e.headers.get("X-Job-ID")??void 0;try{const i=await e.json(),n=i?.error;return new $(n?.message||`Request failed with status ${e.status}`,{status:e.status,code:n?.code,requestId:i?.request_id||o,jobId:i?.job_id||a})}catch{return new $(`Request failed with status ${e.status}`,{status:e.status,requestId:o,jobId:a})}},X=()=>{if(globalThis.crypto&&typeof globalThis.crypto.randomUUID=="function")return globalThis.crypto.randomUUID();if(globalThis.crypto&&typeof globalThis.crypto.getRandomValues=="function"){const e=new Uint8Array(16);globalThis.crypto.getRandomValues(e),e[6]=e[6]&15|64,e[8]=e[8]&63|128;const o=Array.from(e,a=>a.toString(16).padStart(2,"0"));return`${o.slice(0,4).join("")}-${o.slice(4,6).join("")}-${o.slice(6,8).join("")}-${o.slice(8,10).join("")}-${o.slice(10,16).join("")}`}return`${Date.now().toString(36)}-${Math.random().toString(36).slice(2,10)}`};class Y{baseUrl;apiKey;constructor(o){this.baseUrl=u(o.baseUrl),this.apiKey=o.apiKey?.trim()||void 0}async health(){return this.request("/healthz",!1)}async readiness(){return this.request("/readyz",!1)}async voices(o){const a=o?`?language_code=${encodeURIComponent(o)}`:"";return this.request(`/v1/voices${a}`,!0)}async synthesize(o,a){return this.request("/v1/synthesize",!0,{method:"POST",body:JSON.stringify(o),headers:a?{"Idempotency-Key":a}:void 0})}async startVideoLocalization(o,a){const i=new FormData;return i.set("video",o.video),i.set("source_language",o.source_language),i.set("target_language",o.target_language),i.set("generate_subtitles",String(o.generate_subtitles)),i.set("burn_subtitles",String(o.burn_subtitles)),o.target_voice_name&&i.set("target_voice_name",o.target_voice_name),o.target_voice_language_code&&i.set("target_voice_language_code",o.target_voice_language_code),o.metadata?.client_reference_id&&i.set("client_reference_id",o.metadata.client_reference_id),this.request("/v1/video-localization/jobs",!0,{method:"POST",body:i,headers:a?{"Idempotency-Key":a}:void 0})}async videoLocalizationJob(o){return this.request(`/v1/video-localization/jobs/${encodeURIComponent(o)}`,!0)}async request(o,a,i={}){const n=new Headers(i.headers);n.set("Accept","application/json"),i.body&&!(i.body instanceof FormData)&&n.set("Content-Type","application/json"),a&&this.apiKey&&n.set("Authorization",`Bearer ${this.apiKey}`),n.set("X-Request-ID",`web_${X()}`);let d;try{d=await fetch(`${this.baseUrl}${o}`,{...i,headers:n})}catch{throw new $(`Cannot reach backend at ${this.baseUrl}. Check the API base URL and CORS settings.`)}if(!d.ok)throw await K(d);return d.json()}}const c={baseUrl:"voice-ai.base-url",history:"voice-ai.history",videoHistory:"voice-ai.video-history",demoUser:"voice-ai.demo-user"};function T(e){return["localhost","127.0.0.1","::1","[::1]"].includes(e)}function Q(e){try{return T(new URL(e).hostname)}catch{return!1}}function Z(){if(typeof window>"u")return"http://localhost:8080";const{hostname:e,protocol:o}=window.location;return T(e)?"http://localhost:8080":u(`${o==="https:"?"https":"http"}://${e}:8080`)}const q=Z();function ee(){const e=localStorage.getItem(c.baseUrl);return!e||typeof window<"u"&&!T(window.location.hostname)&&Q(e)?q:u(e)}const p=[{name:"en-US-Standard-C",language_codes:["en-US"],ssml_gender:"FEMALE",natural_sample_rate_hz:24e3,supported_encodings:["MP3","LINEAR16","OGG_OPUS"]},{name:"en-US-Standard-D",language_codes:["en-US"],ssml_gender:"MALE",natural_sample_rate_hz:24e3,supported_encodings:["MP3","LINEAR16","OGG_OPUS"]},{name:"vi-VN-Standard-A",language_codes:["vi-VN"],ssml_gender:"FEMALE",natural_sample_rate_hz:24e3,supported_encodings:["MP3","LINEAR16"]}],S="Xin chao. Day la ban thuyet minh tieng Viet duoc tao tu video goc tieng Trung hoac tieng Anh. Ban co the xem lai loi dich, phu de, giong doc va tep xuat ban truoc khi tai ve.",k=`1
00:00:00,000 --> 00:00:04,000
Xin chao. Day la ban thuyet minh tieng Viet.

2
00:00:04,000 --> 00:00:08,000
Kiem tra phu de, giong doc va video cuoi cung truoc khi tai ve.`,t={activeWorkflow:"video",authMode:"register",showAuthPanel:!1,demoUser:localStorage.getItem(c.demoUser)||"",baseUrl:ee(),apiKey:"",voices:p,readiness:null,voiceLoading:!1,synthLoading:!1,selectedVoiceName:p[0].name,selectedLanguage:p[0].language_codes[0],encoding:"MP3",mode:"text",text:"Paste a short product script here to create a Vietnamese voiceover preview while the video pipeline is being tested.",speakingRate:1,pitch:0,volumeGainDb:0,clientReferenceId:"",latest:null,latestAudioUrl:"",error:"",history:x(c.history,[]),videoFile:null,videoSourceLanguage:"auto",videoTargetVoiceName:"vi-VN-Standard-A",videoBurnSubtitles:!0,videoClientReferenceId:"",videoLoading:!1,videoJob:null,videoError:"",videoScript:"",videoSrt:"",videoHistory:x(c.videoHistory,[])},R=document.querySelector("#app");if(!R)throw new Error("Missing #app root");const te=R,_=()=>new Y({baseUrl:t.baseUrl,apiKey:t.apiKey});function x(e,o){try{return JSON.parse(localStorage.getItem(e)||"")}catch{return o}}function oe(){localStorage.setItem(c.baseUrl,t.baseUrl)}function M(){localStorage.setItem(c.history,JSON.stringify(t.history.slice(0,12)))}function C(){localStorage.setItem(c.videoHistory,JSON.stringify(t.videoHistory.slice(0,12)))}function g(){return t.voices.find(e=>e.name===t.selectedVoiceName)||t.voices[0]||p[0]}function h(){const e=t.voices.filter(o=>o.language_codes.some(a=>a.toLowerCase().startsWith("vi")));return e.length?e:p.filter(o=>o.language_codes.some(a=>a.toLowerCase().startsWith("vi")))}function P(){return h().find(e=>e.name===t.videoTargetVoiceName)||h()[0]||p[2]}function j(){return g().supported_encodings?.length?g().supported_encodings:["MP3","LINEAR16","OGG_OPUS"]}function z(e){const o=e.language_codes.join(", "),a=e.ssml_gender?`, ${e.ssml_gender.toLowerCase()}`:"";return`${e.name} (${o}${a})`}function w(e,o=""){return typeof e=="number"?`${e.toLocaleString()}${o}`:"Not reported"}function L(e){if(e instanceof $){const o=[e.code,e.status?`HTTP ${e.status}`:"",e.requestId?`request ${e.requestId}`:""].filter(Boolean).join(" - ");return o?`${e.message} (${o})`:e.message}return e instanceof Error?e.message:"Unexpected error"}async function E(){t.voiceLoading=!0,t.error="",t.videoError="",r();try{const e=_(),[o,a]=await Promise.allSettled([e.readiness(),e.voices()]);o.status==="fulfilled"&&(t.readiness=o.value),a.status==="fulfilled"&&a.value.voices.length&&(t.voices=a.value.voices,t.voices.some(n=>n.name===t.selectedVoiceName)||(t.selectedVoiceName=t.voices[0].name,t.selectedLanguage=t.voices[0].language_codes[0]),h().some(n=>n.name===t.videoTargetVoiceName)||(t.videoTargetVoiceName=h()[0]?.name||p[2].name));const i=[o,a].find(n=>n.status==="rejected");if(i?.status==="rejected"){const n=`${L(i.reason)} Fallback voices remain available for prototype testing.`;t.error=n,t.videoError=n}}finally{t.voiceLoading=!1,r()}}async function ae(){const e=t.text.trim();if(!e){t.error="Enter text or SSML before synthesizing.",r();return}if(e.length>5e3){t.error="Input exceeds the MVP limit of 5,000 characters.",r();return}const o=g(),a=t.selectedLanguage||o.language_codes[0];t.synthLoading=!0,t.error="",r();try{const i=await _().synthesize({text:t.mode==="text"?e:null,ssml:t.mode==="ssml"?e:null,voice:{language_code:a,name:o.name,ssml_gender:o.ssml_gender},audio:{encoding:t.encoding,speaking_rate:t.speakingRate,pitch:t.pitch,volume_gain_db:t.volumeGainDb,sample_rate_hz:o.natural_sample_rate_hz},metadata:{client_reference_id:t.clientReferenceId.trim()||void 0}},t.clientReferenceId.trim()||void 0),n=G(t.baseUrl,i.audio_url,i.audio_path);t.latest=i,t.latestAudioUrl=n,t.history=[{jobId:i.job_id,status:i.status,textPreview:e.slice(0,120),voice:o.name,language:a,encoding:t.encoding,audioUrl:n,latencyMs:i.latency_ms,durationMs:i.duration_ms,provider:i.provider?.name,createdAt:new Date().toISOString()},...t.history].slice(0,12),M()}catch(i){t.error=L(i)}finally{t.synthLoading=!1,r()}}async function ie(){if(!t.videoFile){t.videoError="Upload a Chinese or English video before starting localization. Use the quick TTS tab if you only want a no-file audio test.",r();return}const e=P();t.videoLoading=!0,t.videoError="",t.videoJob={job_id:"local_preview",status:"processing",progress:12,stage:"Uploading source video"},r();try{const o=await _().startVideoLocalization({video:t.videoFile,source_language:t.videoSourceLanguage,target_language:"vi",target_voice_name:e.name,target_voice_language_code:e.language_codes[0],generate_subtitles:!0,burn_subtitles:t.videoBurnSubtitles,metadata:{client_reference_id:t.videoClientReferenceId.trim()||void 0}},t.videoClientReferenceId.trim()||void 0);N(o),A(o.status)||window.setTimeout(()=>{D(o.job_id)},1200)}catch(o){t.videoError=`${L(o)} Video backend may not be available yet. The prototype UI stays usable for upload, language, voice, subtitle, and artifact review testing.`,t.videoJob={job_id:"demo_video_preview",status:"needs_review",progress:58,stage:"Demo review state: backend unavailable",source_language:t.videoSourceLanguage,target_language:"vi",script:{vietnamese_text:S,srt:k,editable:!1}},t.videoScript=S,t.videoSrt=k}finally{t.videoLoading=!1,r()}}async function D(e){try{const o=await _().videoLocalizationJob(e);N(o),r(),A(o.status)||window.setTimeout(()=>{D(e)},2500)}catch(o){t.videoError=L(o),r()}}function A(e){return["succeeded","failed","needs_review","canceled"].includes(e)}function N(e){if(t.videoJob=e,t.videoScript=e.script?.vietnamese_text||t.videoScript,t.videoSrt=e.script?.srt||t.videoSrt,e.job_id&&A(e.status)){const o=O(e);t.videoHistory=[{jobId:e.job_id,status:e.status,sourceLanguage:t.videoSourceLanguage,targetVoice:P().name,fileName:t.videoFile?.name||"Uploaded video",audioUrl:o.audio,videoUrl:o.video,srtUrl:o.srt,createdAt:new Date().toISOString()},...t.videoHistory.filter(a=>a.jobId!==e.job_id)].slice(0,12),C()}}function O(e=t.videoJob){const o=e?.artifacts;return{transcript:m(t.baseUrl,o?.transcript_url,o?.transcript_path),srt:m(t.baseUrl,o?.srt_url,o?.srt_path),audio:m(t.baseUrl,o?.audio_url,o?.audio_path,"audio"),video:m(t.baseUrl,o?.video_url,o?.video_path)}}function r(){const e=t.readiness?.status||"demo",o=t.readiness?.provider;te.innerHTML=`
    <a class="skip-link" href="#studio">Skip to prototype studio</a>
    <header class="top-nav">
      <a class="brand" href="#prototype" aria-label="Voice AI home">
        <span class="brand-mark" aria-hidden="true">VA</span>
        <span>Voice AI</span>
      </a>
      <nav class="nav-links" aria-label="Primary">
        <a href="#product">Product</a>
        <a href="#workflow">Workflow</a>
        <a href="#pricing">Pricing</a>
        <a href="#security">Security</a>
        <a href="#docs">Docs</a>
      </nav>
      <div class="nav-actions">
        <button class="ghost-button" id="login-button" type="button">Login</button>
        <button class="nav-signup" id="signup-button" type="button">Sign up</button>
      </div>
    </header>

    <main>
      <section id="prototype" class="hero-studio" aria-labelledby="hero-title">
        <div class="hero-copy">
          <p class="eyebrow">Instant Vietnamese localization prototype</p>
          <h1 id="hero-title">Vietnamese video localization test studio</h1>
          <p class="hero-lede">
            Chinese/English video -> Vietnamese script, subtitles, voice dub, and MP4. Upload a clip and test the core flow first.
          </p>
          <div class="hero-actions">
            <a class="primary-link" href="#studio">Test video prototype</a>
            <button class="secondary-button" id="hero-tts-button" type="button" aria-label="Open quick TTS demo">Try quick TTS</button>
          </div>
          <div class="proof-strip" aria-label="Product capabilities">
            <span><b>Input</b> Chinese or English source video</span>
            <span><b>Review</b> Vietnamese script and subtitle timing</span>
            <span><b>Export</b> Dubbed audio and final MP4</span>
          </div>
        </div>

        <section id="studio" class="studio-shell" aria-label="Prototype workspace" data-testid="prototype-studio">
          <div class="studio-toolbar">
            <div>
              <span class="mini-label">Demo workspace</span>
              <strong>${t.demoUser?s(t.demoUser):"Public prototype"}</strong>
            </div>
            <div class="studio-stats" aria-label="Prototype status summary">
              <span>Pipeline 7 steps</span>
              <span>Target vi-VN</span>
              <span>Artifacts 4</span>
            </div>
            <div class="health-pill ${e==="ready"?"is-ready":""}" aria-live="polite">
              <span class="status-dot" aria-hidden="true"></span>
              ${s(e)}
            </div>
          </div>

          <form id="settings-form" class="settings-grid" aria-label="API connection settings">
            <label class="field">
              <span>Backend API URL</span>
              <input id="base-url" type="url" value="${s(t.baseUrl)}" autocomplete="url" />
            </label>
            <label class="field">
              <span>Backend API key</span>
              <input id="api-key" type="password" value="${s(t.apiKey)}" autocomplete="off" placeholder="Session only; never stored" />
            </label>
            <button class="secondary-button" type="submit" ${t.voiceLoading?"disabled":""}>
              ${t.voiceLoading?"Checking...":"Refresh backend"}
            </button>
          </form>

          <div class="workflow-switch" role="tablist" aria-label="Prototype workflow">
            <button id="workflow-video" class="${t.activeWorkflow==="video"?"is-active":""}" type="button" role="tab" aria-selected="${t.activeWorkflow==="video"}" data-testid="workflow-video-localization-tab">Video localization</button>
            <button id="workflow-tts" class="${t.activeWorkflow==="tts"?"is-active":""}" type="button" role="tab" aria-selected="${t.activeWorkflow==="tts"}" aria-label="Open quick TTS workflow tab" data-testid="workflow-quick-tts-tab">Quick TTS</button>
          </div>

          <div class="workspace-grid">
            <div class="composer-panel">
              ${t.activeWorkflow==="video"?ne():se()}
            </div>
            <aside class="result-panel" aria-label="Output, status, and history">
              ${t.activeWorkflow==="video"?le():re()}
              ${ce(o)}
              ${ue()}
            </aside>
          </div>
        </section>
      </section>

      <section id="product" class="content-section product-grid">
        <div>
          <p class="eyebrow">Product-led localization</p>
          <h2>Built for teams turning global video into Vietnamese-ready assets.</h2>
        </div>
        ${U("01","Fast prototype loop","Upload a source video, confirm language, choose a Vietnamese voice, and see review states without digging through API docs.")}
        ${U("02","Production artifact model","Transcript, SRT, dubbed audio, render logs, and final MP4 are first-class outputs instead of hidden background files.")}
        ${U("03","Studio and API posture","The interface is usable by content teams while preserving backend-configured APIs for developer integration.")}
      </section>

      <section id="workflow" class="content-section workflow-explainer">
        <div>
          <p class="eyebrow">Workflow</p>
          <h2>From source video to Vietnamese delivery package.</h2>
        </div>
        <ol class="step-list">
          <li><span>1</span><strong>Upload</strong><p>Drop in a Chinese or English video and choose auto-detect or a fixed source language.</p></li>
          <li><span>2</span><strong>Review text</strong><p>Inspect Vietnamese script and subtitle timing before handoff or final rendering.</p></li>
          <li><span>3</span><strong>Dub</strong><p>Generate Vietnamese voiceover with clear voice metadata, rate, pitch, and provider status.</p></li>
          <li><span>4</span><strong>Export</strong><p>Download transcript, SRT, audio, and final MP4 when the backend publishes artifacts.</p></li>
        </ol>
      </section>

      <section id="pricing" class="content-section">
        <div class="section-kicker">
          <p class="eyebrow">Pricing</p>
          <h2>Transparent tiers for prototype, creator, studio, and enterprise use.</h2>
        </div>
        <div class="pricing-grid">
          ${f("Free Demo","$0","Prototype testing",["Short TTS previews","Video UI demo states","No commercial usage claim"])}
          ${f("Creator","$29","Solo production",["Monthly voice minutes","Transcript and SRT downloads","Commercial rights subject to provider terms"])}
          ${f("Studio","$149","Team localization",["Workspace history","Batch review workflow","Priority render queue when backend supports it"])}
          ${f("Enterprise","Custom","Security and scale",["Backend-managed credentials","Private deployment options","Audit logs, Cloud logs, and MLflow observability"])}
        </div>
      </section>

      <section id="security" class="content-section trust-grid">
        <div>
          <p class="eyebrow">Trust and security</p>
          <h2>Designed around backend-owned secrets and observable processing.</h2>
          <p>The browser never receives OpenAI, Google, or cloud provider keys. Optional backend API keys are session-only and are not persisted.</p>
        </div>
        ${y("Creators","Preview dubs and subtitles before publishing campaign or education videos.")}
        ${y("Education","Localize lessons and training clips while keeping script review visible.")}
        ${y("Sales teams","Adapt product walkthroughs for Vietnamese prospects without manual media assembly.")}
        ${y("Agencies","Track source file, status, voice, and artifacts for client localization jobs.")}
      </section>

      <section id="docs" class="content-section docs-panel">
        <div>
          <p class="eyebrow">Docs</p>
          <h2>Backend assumptions are explicit.</h2>
          <p>TTS follows the documented /v1/voices and /v1/synthesize contract. Video localization currently assumes /v1/video-localization/jobs plus job polling until the backend contract is finalized.</p>
        </div>
        <code>VITE_API_BASE_URL=http://&lt;api-host&gt;:8080 npm run dev -- --host 0.0.0.0 --port 5173</code>
      </section>
    </main>

    ${ge()}
  `,he()}function se(){const o=g().language_codes,a=t.text.length;return`
    <form id="synthesis-form" class="synthesis-form" aria-label="Synthesize speech">
      <div class="prototype-header">
        <span class="mini-label">No-file audio test</span>
        <h2>Quick TTS studio</h2>
        <p>Generate a short voiceover preview when you want to test audio without uploading a video file.</p>
      </div>
      <div class="mode-row" role="radiogroup" aria-label="Input mode">
        <label><input type="radio" name="mode" value="text" ${t.mode==="text"?"checked":""} /> Plain text</label>
        <label><input type="radio" name="mode" value="ssml" ${t.mode==="ssml"?"checked":""} /> SSML</label>
      </div>
      <label class="field">
        <span>${t.mode==="ssml"?"SSML input":"Script input"}</span>
        <textarea id="text-input" maxlength="5000" rows="10">${s(t.text)}</textarea>
        <small id="character-count">${a.toLocaleString()} / 5,000 characters</small>
      </label>
      <div class="control-grid">
        <label class="field"><span>Voice</span><select id="voice-select">${t.voices.map(i=>`<option value="${s(i.name)}" ${i.name===t.selectedVoiceName?"selected":""}>${s(z(i))}</option>`).join("")}</select></label>
        <label class="field"><span>Language</span><select id="language-select">${o.map(i=>`<option value="${s(i)}" ${i===t.selectedLanguage?"selected":""}>${s(i)}</option>`).join("")}</select></label>
        <label class="field"><span>Encoding</span><select id="encoding-select">${j().map(i=>`<option value="${s(i)}" ${i===t.encoding?"selected":""}>${s(i)}</option>`).join("")}</select></label>
        <label class="field"><span>Client reference</span><input id="client-reference-id" type="text" value="${s(t.clientReferenceId)}" placeholder="script-123" /></label>
      </div>
      <div class="slider-grid">
        ${I("speaking-rate","Speaking rate",t.speakingRate,.25,4,.05,"x")}
        ${I("pitch","Pitch",t.pitch,-20,20,.5," st")}
        ${I("volume-gain-db","Volume gain",t.volumeGainDb,-16,16,.5," dB")}
      </div>
      ${t.error?`<div class="error-banner" role="alert">${s(t.error)}</div>`:""}
      <div class="action-row">
        <button class="primary-button" type="submit" data-testid="generate-tts-preview" ${t.synthLoading?"disabled":""}>${t.synthLoading?"Synthesizing...":"Generate TTS preview"}</button>
        <p class="request-note">Native audio controls, no autoplay, downloadable when backend returns an artifact.</p>
      </div>
    </form>
  `}function ne(){const e=h(),o=t.videoFile;return`
    <form id="video-form" class="synthesis-form" aria-label="Localize video to Vietnamese">
      <div class="prototype-header">
        <span class="mini-label">Core test flow</span>
        <h2>Video to Vietnamese studio</h2>
        <p>Start here. Upload a source clip, choose the language and Vietnamese voice, then inspect the translation package before final export.</p>
      </div>
      <label class="field file-field command-upload">
        <span>Source video</span>
        <input id="video-file" type="file" accept="video/mp4,video/quicktime,video/webm,video/*" aria-describedby="video-file-help" />
        <strong>${o?s(o.name):"Drop a Chinese or English video into the localization queue"}</strong>
        <small id="video-file-help">${o?`${w(o.size," bytes")} selected. Start localization when ready.`:"MP4, MOV, or WebM. Use a short clip for the fastest prototype feedback."}</small>
      </label>
      <div class="control-grid video-controls">
        <label class="field"><span>Source language</span><select id="video-source-language">
          <option value="auto" ${t.videoSourceLanguage==="auto"?"selected":""}>Auto detect Chinese or English</option>
          <option value="zh" ${t.videoSourceLanguage==="zh"?"selected":""}>Chinese</option>
          <option value="en" ${t.videoSourceLanguage==="en"?"selected":""}>English</option>
        </select></label>
        <label class="field"><span>Target</span><input type="text" value="Vietnamese script, SRT, dub, MP4" disabled /></label>
        <label class="field"><span>Vietnamese voice</span><select id="video-target-voice">${e.map(a=>`<option value="${s(a.name)}" ${a.name===P().name?"selected":""}>${s(z(a))}</option>`).join("")}</select></label>
        <label class="field"><span>Client reference</span><input id="video-client-reference-id" type="text" value="${s(t.videoClientReferenceId)}" placeholder="pilot-video-01" /></label>
      </div>
      <label class="check-row">
        <input id="video-burn-subtitles" type="checkbox" ${t.videoBurnSubtitles?"checked":""} />
        Burn Vietnamese subtitles into final video when backend supports rendering
      </label>
      ${t.videoError?`<div class="error-banner" role="alert">${s(t.videoError)}</div>`:""}
      <div class="action-row">
        <button class="primary-button" type="submit" data-testid="start-video-localization" ${t.videoLoading?"disabled":""}>${t.videoLoading?"Starting localization...":"Start Vietnamese localization"}</button>
        <button class="secondary-button" id="load-demo-review" type="button">View demo review state</button>
      </div>
      <div class="pipeline-preview" aria-label="Localization pipeline stages">
        ${F(t.videoJob?.stage)}
      </div>
    </form>
  `}function re(){return`
    <section class="panel-section">
      <div class="section-heading"><h2>TTS output</h2><span>${t.latest?.status||"No job yet"}</span></div>
      ${t.synthLoading?B():t.latest?de():'<div class="empty-state"><p>Generate a short voiceover when you want to test without a video file.</p></div>'}
    </section>
  `}function de(){const e=t.latest,o=t.latestAudioUrl;return`
    <div class="audio-card">
      ${o?`<audio controls preload="metadata" src="${v(o)}">Your browser does not support audio playback.</audio><a class="download-link" href="${v(o)}" download>Download audio</a>`:'<div class="empty-state small"><p>The backend did not return an audio URL or path.</p></div>'}
      <dl class="metadata-list">
        <div><dt>Job ID</dt><dd data-testid="tts-job-id">${s(e.job_id)}</dd></div>
        <div><dt>Latency</dt><dd>${w(e.latency_ms," ms")}</dd></div>
        <div><dt>Duration</dt><dd>${w(e.duration_ms," ms")}</dd></div>
        <div><dt>Audio</dt><dd>${s(e.audio?.encoding||t.encoding)} · ${w(e.audio?.bytes," bytes")}</dd></div>
        <div><dt>Request ID</dt><dd>${s(e.observability?.request_id||"Not reported")}</dd></div>
      </dl>
    </div>
  `}function le(){const e=t.videoJob,o=O(e),a=Math.max(0,Math.min(100,Math.round(e?.progress??(e?.status==="succeeded"?100:0))));return`
    <section class="panel-section">
      <div class="section-heading"><h2>Localization output</h2><span>${s(e?.status||"Ready to test")}</span></div>
      ${t.videoLoading?B():e?`<div class="video-job-card">
                <div class="progress-shell" aria-label="Video localization progress"><span style="width: ${a}%"></span></div>
                <p class="stage-line">${s(e.stage||e.message||"Waiting for backend status updates.")}</p>
                <div class="agent-plan" aria-label="Processing plan">
                  ${F(e.stage)}
                </div>
                <div class="artifact-grid">
                  ${b("Transcript",o.transcript)}
                  ${b("SRT",o.srt)}
                  ${b("Vietnamese audio",o.audio)}
                  ${b("Final MP4",o.video)}
                </div>
                ${o.audio?`<audio controls preload="metadata" src="${v(o.audio)}">Your browser does not support audio playback.</audio>`:""}
                ${o.video?`<video controls preload="metadata" src="${v(o.video)}">Your browser does not support video playback.</video>`:'<div class="video-placeholder">Final video preview appears here when the backend publishes MP4 output.</div>'}
                <label class="field"><span>Vietnamese script preview</span><textarea id="video-script-editor" rows="6" placeholder="Vietnamese script appears here after transcription and translation.">${s(t.videoScript)}</textarea></label>
                <label class="field"><span>Vietnamese SRT preview</span><textarea id="video-srt-editor" rows="6" placeholder="Timed Vietnamese subtitles appear here.">${s(t.videoSrt)}</textarea></label>
                <dl class="metadata-list">
                  <div><dt>Job ID</dt><dd data-testid="video-job-id">${s(e.job_id)}</dd></div>
                  <div><dt>Source</dt><dd>${s(e.source_language||t.videoSourceLanguage)}</dd></div>
                  <div><dt>Target</dt><dd>${s(e.target_language||"vi")}</dd></div>
                  <div><dt>Request ID</dt><dd>${s(e.observability?.request_id||"Not reported")}</dd></div>
                </dl>
              </div>`:'<div class="empty-state"><p>Upload a short video or open the demo review state. This is the first thing to test on the public link.</p></div>'}
    </section>
  `}function ce(e){return`
    <section class="panel-section compact">
      <div class="section-heading"><h2>Backend status</h2><button class="text-button" id="status-refresh" type="button">Check</button></div>
      <dl class="metadata-list">
        <div><dt>Provider</dt><dd>${s(e?.name||"Fallback/demo")}${e?.fallback?" (fallback)":""}</dd></div>
        <div><dt>Provider ready</dt><dd>${e?.ready===void 0?"Unknown":e.ready?"Yes":"No"}</dd></div>
        <div><dt>Storage</dt><dd>${s(t.readiness?.storage?.mode||"Unknown")} ${t.readiness?.storage?.ready===!1?"(not ready)":""}</dd></div>
        <div><dt>MLflow</dt><dd>${t.readiness?.mlflow?.configured?"Configured":"Not configured"} ${t.readiness?.mlflow?.ready===!1?"(not ready)":""}</dd></div>
      </dl>
    </section>
  `}function ue(){const e=t.activeWorkflow==="video";return`
    <section class="panel-section compact">
      <div class="section-heading">
        <h2>${e?"Video jobs":"TTS history"}</h2>
        <button class="text-button" id="clear-history" type="button" ${e?t.videoHistory.length?"":"disabled":t.history.length?"":"disabled"}>Clear</button>
      </div>
      ${e?t.videoHistory.length?`<ol class="history-list">${t.videoHistory.map(ve).join("")}</ol>`:'<div class="empty-state small"><p>No video jobs in this browser yet.</p></div>':t.history.length?`<ol class="history-list">${t.history.map(pe).join("")}</ol>`:'<div class="empty-state small"><p>No TTS jobs in this browser yet.</p></div>'}
    </section>
  `}function I(e,o,a,i,n,d,l){return`<label class="field range-field"><span>${o}</span><input id="${e}" type="range" min="${i}" max="${n}" step="${d}" value="${a}" /><output for="${e}">${a}${l}</output></label>`}function B(){return'<div class="skeleton-block" aria-live="polite"><span></span><span></span><span></span></div>'}function b(e,o){return o?`<a class="download-link artifact-card" href="${v(o)}" download><span>${s(e)}</span><small>Ready</small></a>`:`<span class="artifact-missing artifact-card" aria-disabled="true"><span>${s(e)}</span><small>Pending</small></span>`}function F(e){const o=(e||"").toLowerCase(),a=[["Upload","source file"],["Extract","audio track"],["Transcribe","source speech"],["Translate","Vietnamese script"],["Subtitle","timed SRT"],["Dub","Vietnamese voice"],["Render","final MP4"]],i=Math.max(0,a.findIndex(([n])=>o.includes(n.toLowerCase())));return a.map(([n,d],l)=>{const J=l===i,H=o.length>0&&l<i;return`<div class="plan-step ${J?"is-active":""} ${H?"is-done":""}"><span>${l+1}</span><strong>${n}</strong><small>${d}</small></div>`}).join("")}function pe(e){const o=new Date(e.createdAt).toLocaleString();return`<li><div><strong>${s(e.jobId)}</strong><p>${s(e.textPreview)}</p><span>${s(e.voice)} · ${s(e.encoding)} · ${s(o)}</span></div>${e.audioUrl?`<a href="${v(e.audioUrl)}" download>Download</a>`:""}</li>`}function ve(e){const o=new Date(e.createdAt).toLocaleString(),a=e.videoUrl||e.audioUrl||e.srtUrl;return`<li><div><strong>${s(e.jobId)}</strong><p>${s(e.fileName)} with ${s(e.targetVoice)}</p><span>${s(e.status)} · ${s(e.sourceLanguage)} to vi · ${s(o)}</span></div>${a?`<a href="${v(a)}" download>Download</a>`:""}</li>`}function U(e,o,a){return`<article class="feature-card"><span>${e}</span><h3>${s(o)}</h3><p>${s(a)}</p></article>`}function f(e,o,a,i){return`<article class="pricing-card"><h3>${s(e)}</h3><strong>${s(o)}</strong><p>${s(a)}</p><ul>${i.map(n=>`<li>${s(n)}</li>`).join("")}</ul></article>`}function y(e,o){return`<article class="trust-item"><h3>${s(e)}</h3><p>${s(o)}</p></article>`}function ge(){if(!t.showAuthPanel)return"";const e=t.authMode==="register";return`
    <div class="auth-backdrop" role="dialog" aria-modal="true" aria-labelledby="auth-title">
      <form id="auth-form" class="auth-card">
        <button class="auth-close" id="auth-close" type="button" aria-label="Close auth panel">Close</button>
        <p class="eyebrow">Demo workspace</p>
        <h2 id="auth-title">${e?"Create a demo account":"Login to demo workspace"}</h2>
        <p>No backend auth endpoint is documented yet. This creates a local demo identity only and stores no secrets.</p>
        <label class="field"><span>Email</span><input id="auth-email" type="email" autocomplete="email" placeholder="you@company.com" required /></label>
        <label class="field"><span>Password</span><input id="auth-password" type="password" autocomplete="${e?"new-password":"current-password"}" placeholder="Not sent to backend in demo mode" required /></label>
        <button class="primary-button" type="submit">${e?"Enter demo workspace":"Login to demo"}</button>
        <button class="text-button" id="auth-toggle" type="button">${e?"Use login instead":"Create demo account"}</button>
      </form>
    </div>
  `}function he(){document.querySelector("#workflow-tts")?.addEventListener("click",()=>{t.activeWorkflow="tts",r()}),document.querySelector("#workflow-video")?.addEventListener("click",()=>{t.activeWorkflow="video",r()}),document.querySelector("#hero-tts-button")?.addEventListener("click",()=>{t.activeWorkflow="tts",document.querySelector("#studio")?.scrollIntoView({behavior:"smooth"}),r()}),document.querySelector("#login-button")?.addEventListener("click",()=>{t.authMode="login",t.showAuthPanel=!0,r()}),document.querySelector("#signup-button")?.addEventListener("click",()=>{t.authMode="register",t.showAuthPanel=!0,r()}),document.querySelector("#auth-close")?.addEventListener("click",()=>{t.showAuthPanel=!1,r()}),document.querySelector("#auth-toggle")?.addEventListener("click",()=>{t.authMode=t.authMode==="register"?"login":"register",r()}),document.querySelector("#auth-form")?.addEventListener("submit",e=>{e.preventDefault();const o=document.querySelector("#auth-email")?.value||"Demo user";t.demoUser=o,localStorage.setItem(c.demoUser,o),t.showAuthPanel=!1,r()}),document.querySelector("#settings-form")?.addEventListener("submit",e=>{e.preventDefault(),t.baseUrl=u(document.querySelector("#base-url")?.value||q),t.apiKey=document.querySelector("#api-key")?.value||"",oe(),E()}),document.querySelector("#synthesis-form")?.addEventListener("submit",e=>{e.preventDefault(),ae()}),document.querySelector("#video-form")?.addEventListener("submit",e=>{e.preventDefault(),ie()}),document.querySelector("#load-demo-review")?.addEventListener("click",()=>{t.videoJob={job_id:"demo_video_preview",status:"needs_review",progress:72,stage:"Demo review state: Vietnamese script and subtitles ready",source_language:t.videoSourceLanguage,target_language:"vi",script:{vietnamese_text:S,srt:k,editable:!1}},t.videoScript=S,t.videoSrt=k,r()}),document.querySelectorAll('input[name="mode"]').forEach(e=>{e.addEventListener("change",()=>{t.mode=e.value==="ssml"?"ssml":"text",r()})}),document.querySelector("#text-input")?.addEventListener("input",e=>{t.text=e.target.value;const o=document.querySelector("#character-count");o&&(o.textContent=`${t.text.length.toLocaleString()} / 5,000 characters`)}),document.querySelector("#voice-select")?.addEventListener("change",e=>{t.selectedVoiceName=e.target.value;const o=g();t.selectedLanguage=o.language_codes[0];const a=j();a.includes(t.encoding)||(t.encoding=a[0]),r()}),document.querySelector("#language-select")?.addEventListener("change",e=>{t.selectedLanguage=e.target.value}),document.querySelector("#encoding-select")?.addEventListener("change",e=>{t.encoding=e.target.value}),document.querySelector("#client-reference-id")?.addEventListener("input",e=>{t.clientReferenceId=e.target.value}),document.querySelector("#video-file")?.addEventListener("change",e=>{t.videoFile=e.target.files?.[0]||null,r()}),document.querySelector("#video-source-language")?.addEventListener("change",e=>{t.videoSourceLanguage=e.target.value}),document.querySelector("#video-target-voice")?.addEventListener("change",e=>{t.videoTargetVoiceName=e.target.value}),document.querySelector("#video-client-reference-id")?.addEventListener("input",e=>{t.videoClientReferenceId=e.target.value}),document.querySelector("#video-burn-subtitles")?.addEventListener("change",e=>{t.videoBurnSubtitles=e.target.checked}),document.querySelector("#video-script-editor")?.addEventListener("input",e=>{t.videoScript=e.target.value}),document.querySelector("#video-srt-editor")?.addEventListener("input",e=>{t.videoSrt=e.target.value}),V("#speaking-rate",e=>t.speakingRate=e),V("#pitch",e=>t.pitch=e),V("#volume-gain-db",e=>t.volumeGainDb=e),document.querySelector("#status-refresh")?.addEventListener("click",()=>{E()}),document.querySelector("#clear-history")?.addEventListener("click",()=>{t.activeWorkflow==="tts"?(t.history=[],M()):(t.videoHistory=[],C()),r()})}function V(e,o){document.querySelector(e)?.addEventListener("input",a=>{const i=a.target,n=Number(i.value);o(n);const d=i.closest(".range-field")?.querySelector("output");if(d){const l=e==="#speaking-rate"?"x":e==="#pitch"?" st":" dB";d.textContent=`${n}${l}`}})}function s(e){return e.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;")}function v(e){return s(e).replace(/`/g,"&#096;")}r();E();
