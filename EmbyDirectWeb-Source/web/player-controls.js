(function(root){
'use strict';
function seekTarget(current,delta,duration){const target=Math.max(0,Math.round(Number(current)+delta*1000));return Number(duration)>0?Math.min(target,Math.max(0,Number(duration)-1)):target;}
function preferredSubtitle(tracks){return tracks.find(t=>t.supported&&t.default)||tracks.find(t=>t.supported)||null;}
if(typeof module==='object'&&module.exports)module.exports={seekTarget,preferredSubtitle};else root.PlayerControls={seekTarget,preferredSubtitle};
})(typeof window==='object'?window:globalThis);
