import net from "node:net";
import tls from "node:tls";
import { createHash, createHmac, pbkdf2Sync, randomBytes, timingSafeEqual } from "node:crypto";
const dbUrl=process.env.DATABASE_URL, apiKey=process.env.MEMORY_GATEWAY_API_KEY;
if(!dbUrl)throw new Error("DATABASE_URL missing");
if(!apiKey||apiKey.length<64)throw new Error("MEMORY_GATEWAY_API_KEY missing or too short");
const expected=createHash("sha256").update(apiKey).digest();
const cstr=s=>Buffer.from(s+"\0");
const msg=(t,p)=>{const h=Buffer.alloc(5);h[0]=t.charCodeAt(0);h.writeInt32BE(p.length+4,1);return Buffer.concat([h,p]);};
const mac=(k,v)=>createHmac("sha256",k).update(v).digest(),sha=v=>createHash("sha256").update(v).digest();
class Reader{
 constructor(s){this.s=s;this.b=Buffer.alloc(0);this.q=[];this.w=[];this.err=null;s.on("data",d=>{this.b=Buffer.concat([this.b,d]);while(this.b.length>=5){const n=this.b.readInt32BE(1);if(n<4||n>16777216)return this.fail(Error("bad PG frame"));if(this.b.length<n+1)break;const m={t:String.fromCharCode(this.b[0]),p:this.b.subarray(5,n+1)};this.b=this.b.subarray(n+1);const w=this.w.shift();w?w(m):this.q.push(m);}});s.on("error",e=>this.fail(e));s.on("close",()=>this.fail(Error("PG socket closed")));}
 fail(e){if(this.err)return;this.err=e;for(const w of this.w.splice(0))w.reject(e);}
 next(ms=12000){if(this.q.length)return Promise.resolve(this.q.shift());if(this.err)return Promise.reject(this.err);return new Promise((resolve,reject)=>{const done=m=>{clearTimeout(timer);resolve(m)};done.reject=e=>{clearTimeout(timer);reject(e)};const timer=setTimeout(()=>{const i=this.w.indexOf(done);if(i>=0)this.w.splice(i,1);reject(Error("PG timeout"));},ms);this.w.push(done);});}
}
function pgError(p){let i=0,o={};while(i<p.length&&p[i]){const k=String.fromCharCode(p[i++]),e=p.indexOf(0,i);if(e<0)break;o[k]=p.toString("utf8",i,e);i=e+1;}const x=Error(o.M||o.S||"PostgreSQL error");x.code=o.C;return x;}
function event(target,ok,timeout=10000){return new Promise((resolve,reject)=>{const timer=setTimeout(()=>finish(reject,Error(ok+" timeout")),timeout),yes=v=>finish(resolve,v),no=e=>finish(reject,e);function finish(f,v){clearTimeout(timer);target.off(ok,yes);target.off("error",no);f(v);}target.once(ok,yes);target.once("error",no);});}
async function connectDb(){
 const u=new URL(dbUrl),host=u.hostname,port=Number(u.port||5432),user=decodeURIComponent(u.username),pass=decodeURIComponent(u.password),db=decodeURIComponent(u.pathname.slice(1))||user;
 const raw=net.connect({host,port});await event(raw,"connect");raw.setNoDelay(true);let s=raw;
 if(u.searchParams.get("sslmode")!=="disable"){const req=Buffer.alloc(8);req.writeInt32BE(8);req.writeInt32BE(80877103,4);raw.write(req);const reply=await event(raw,"data");if(reply[0]!==83){raw.destroy();throw Error("PG TLS refused");}if(reply.length>1)raw.unshift(reply.subarray(1));s=tls.connect({socket:raw,servername:host,rejectUnauthorized:true});await event(s,"secureConnect");}
 const r=new Reader(s);
 const body=Buffer.concat([Buffer.from([0,3,0,0]),cstr("user"),cstr(user),cstr("database"),cstr(db),cstr("client_encoding"),cstr("UTF8"),Buffer.from([0])]),head=Buffer.alloc(4);head.writeInt32BE(body.length+4);s.write(Buffer.concat([head,body]));
 let scram=null,ready=false;while(!ready){const m=await r.next();if(m.t==="E")throw pgError(m.p);if(m.t==="Z"){ready=true;break;}if(m.t!=="R")continue;const code=m.p.readInt32BE(0);if(code===0)continue;
 if(code===10){const mechs=m.p.subarray(4).toString().split("\0");if(!mechs.includes("SCRAM-SHA-256"))throw Error("SCRAM unavailable");const nonce=randomBytes(18).toString("base64").replace(/=+$/g,""),bare="n=,r="+nonce,first=Buffer.from("n,,"+bare),len=Buffer.alloc(4);len.writeInt32BE(first.length);s.write(msg("p",Buffer.concat([cstr("SCRAM-SHA-256"),len,first])));scram={bare};continue;}
 if(code===11){if(!scram)throw Error("unexpected SCRAM continuation");const sf=m.p.subarray(4).toString(),a=Object.fromEntries(sf.split(",").map(v=>[v[0],v.slice(2)]));if(!a.r||!a.s||!a.i)throw Error("bad SCRAM challenge");const rounds=Number(a.i);if(!Number.isInteger(rounds)||rounds<1||rounds>1000000)throw Error("bad SCRAM rounds");const salted=pbkdf2Sync(pass,Buffer.from(a.s,"base64"),rounds,32,"sha256"),ck=mac(salted,"Client Key"),stored=sha(ck),final="c=biws,r="+a.r,auth=scram.bare+","+sf+","+final,sig=mac(stored,auth),proof=Buffer.alloc(32);for(let i=0;i<32;i++)proof[i]=ck[i]^sig[i];scram.server=mac(mac(salted,"Server Key"),auth);s.write(msg("p",Buffer.from(final+",p="+proof.toString("base64"))));continue;}
 if(code===12){const v=m.p.subarray(4).toString().split(",").find(x=>x.startsWith("v="))?.slice(2),actual=v?Buffer.from(v,"base64"):Buffer.alloc(0);if(!scram?.server||actual.length!==32||!timingSafeEqual(actual,scram.server))throw Error("SCRAM signature mismatch");continue;}
 throw Error("unsupported PG auth method "+code);
 }return {s,r};
}
async function readContext(key){const {s,r}=await connectDb();try{s.write(msg("Q",cstr("SELECT memory_bootstrap_context('"+key+"')::text")));let out=null;while(true){const m=await r.next();if(m.t==="E")throw pgError(m.p);if(m.t==="D"&&m.p.readInt16BE(0)>0){const n=m.p.readInt32BE(2);if(n>=0)out=m.p.toString("utf8",6,6+n);}if(m.t==="Z")break;}return out?JSON.parse(out):null;}finally{s.end();}}
const json=(v,status=200)=>new Response(JSON.stringify(v,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}});
function authorized(req){const h=req.headers.get("authorization")||"";if(!h.startsWith("Bearer "))return false;const v=createHash("sha256").update(h.slice(7)).digest();return v.length===expected.length&&timingSafeEqual(v,expected);}
export default {async fetch(req){const u=new URL(req.url);if(req.method==="GET"&&u.pathname==="/health")return json({ok:true,service:"memory-gateway",version:"1.0.2"});if(!authorized(req))return json({error:"unauthorized"},401);if(req.method!=="GET")return json({error:"method_not_allowed"},405);if(u.pathname!=="/v1/context")return json({error:"not_found"},404);const key=u.searchParams.get("project");if(!key||!/^[a-z0-9][a-z0-9._-]{1,79}$/.test(key))return json({error:"invalid_project_key"},400);try{const context=await readContext(key);return context?json(context):json({error:"project_not_found"},404);}catch(e){console.error("memory gateway query failed",{message:e?.message,code:e?.code});return json({error:"memory_backend_unavailable"},503);}}};
