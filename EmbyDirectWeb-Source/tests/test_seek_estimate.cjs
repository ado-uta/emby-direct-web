const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('web/vendor/502.avplayer.js','utf8');
const begin=source.indexOf('function directwebEstimate(');const end=source.indexOf('const dwBase=',begin);const ctx={};vm.createContext(ctx);vm.runInContext(source.slice(begin,end),ctx);
const f=ctx.directwebEstimate;
assert.equal(f([{pos:0n,time:0n},{pos:1000000n,time:100000n}],80000n,0n,1000000n,500000n),800000n);
assert.equal(f([],80000n,0n,1000000n,500000n),500000n);
assert.equal(f([{pos:500000n,time:50000n},{pos:600000n,time:40000n}],80000n,0n,1000000n,500000n),500000n);
assert.equal(f([{pos:0n,time:0n},{pos:1000000n,time:100000n}],80000n,0n,1000000n,800000n),500000n);
console.log('TS interpolation: linear estimate, missing/non-monotonic fallback, repeated-position fallback PASS');

function simulate(interpolate){let low=0n,high=1129416952n,pos=564708476n;const target=2509000n;const points=[{pos:0n,time:0n}];for(let rounds=1;rounds<30;rounds++){const time=pos*target/1103425580n;points.push({pos,time});if(time<=target&&target-time<10000n)return rounds;if(time>target)high=pos;else low=pos;pos=interpolate?f(points,target-2000n,low,high,pos):(low+high)>>1n;}throw Error('No convergence');}
const binary=simulate(false),interpolated=simulate(true);assert(interpolated<binary);console.log('Synthetic timestamp seek round trips: binary='+binary+', interpolated='+interpolated);

assert.equal(f([{pos:0n,time:0n},{pos:1000000n,time:100000n}],120000n,0n,2000000n,-1n),1200000n);console.log("Warm seek initial estimate reuses timestamp samples PASS");

assert.equal(f([],120000n,0n,2000000n,-1n,650000n),650000n);console.log("Invalid warm samples retain original initial estimate PASS");
