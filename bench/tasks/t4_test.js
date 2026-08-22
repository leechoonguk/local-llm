const {debounce}=require('./sol.js');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 let calls=[]; const d=debounce((x)=>calls.push(x),50);
 d(1);d(2);d(3); await sleep(80); if(JSON.stringify(calls)!=='[3]') throw new Error('trailing '+JSON.stringify(calls));
 calls=[]; const l=debounce((x)=>calls.push(x),50,{leading:true,trailing:false});
 l(1);l(2); await sleep(80); l(3); await sleep(80); if(JSON.stringify(calls)!=='[1,3]') throw new Error('leading '+JSON.stringify(calls));
 calls=[]; const b=debounce((x)=>calls.push(x),50,{leading:true,trailing:true});
 b(1); await sleep(80); if(JSON.stringify(calls)!=='[1]') throw new Error('both-single '+JSON.stringify(calls));
 b(2);b(3); await sleep(80); if(JSON.stringify(calls)!=='[1,2,3]') throw new Error('both-burst '+JSON.stringify(calls));
 calls=[]; const c=debounce((x)=>calls.push(x),50); c(1); c.cancel(); await sleep(80); if(calls.length) throw new Error('cancel');
 console.log('T4 OK');
})().catch(e=>{console.error(e.message);process.exit(1)});
