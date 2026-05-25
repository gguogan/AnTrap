# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Simple browser-based tasks (Tier A) extending the AndroidWorld suite.

Each task reuses `BrowserTask` from `browser.py` for Chrome setup, HTML push,
and `is_successful()` (which fires when any UI element renders the literal
text `Success!`). Subclasses only need to:

  * declare a self-contained HTML/JS page in `HTML`,
  * provide a goal string (with the standard `preamble` opening),
  * render `Success!` somewhere visible when the user completes the task.

Win conditions are intentionally simple: 1-5 click steps, no AI opponent, no
timer, no memory, no arithmetic.
"""

from android_world.task_evals.single.browser import BrowserTask


# =============================================================================
# 1. BrowserClickN — press one button N times
# =============================================================================
class BrowserClickN(BrowserTask):
  """Click a single button N times (N derived from the task seed)."""

  @property
  def goal(self) -> str:
    n = (self.params['browser_task_seed'] % 4) + 3  # 3..6
    return (
        self.preamble
        + f' Then click the big button {n} times.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Click N</title>
<style>body{text-align:center;font-family:sans-serif}
button{font-size:32px;padding:24px 48px;margin-top:40px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div class="msg" id="msg">Clicks: 0</div>
<button onclick="tick()">Press me</button>
<script>
const target=(%%SEED%% % 4)+3;
let n=0;
function tick(){
  n++;
  document.getElementById('msg').innerText =
    n>=target ? 'Success!' : 'Clicks: '+n;
}
</script></body></html>
"""


# =============================================================================
# 2. BrowserFillName — type one word into one field
# =============================================================================
class BrowserFillName(BrowserTask):
  """Type the requested name into an input field and submit."""

  _NAMES = ('Alice', 'Bob', 'Charlie', 'Diana', 'Edward', 'Fiona')

  @property
  def goal(self) -> str:
    name = self._NAMES[self.params['browser_task_seed'] % len(self._NAMES)]
    return (
        self.preamble
        + f' Then type the name "{name}" into the input field and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Fill Name</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
input{font-size:24px;padding:8px;width:60%}
button{font-size:24px;padding:10px 30px;margin-top:20px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<input id="name" type="text" placeholder="Your name"/>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
const names=['Alice','Bob','Charlie','Diana','Edward','Fiona'];
const target=names[%%SEED%% % names.length];
function check(){
  const v=document.getElementById('name').value.trim();
  document.getElementById('msg').innerText = (v===target)?'Success!':'Try again';
}
</script></body></html>
"""


# =============================================================================
# 3. BrowserCheckBoxes — pick 3 specific checkboxes out of 5
# =============================================================================
class BrowserCheckBoxes(BrowserTask):
  """Check three specific checkboxes from a five-item list and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then check the boxes labelled Apple, Banana, and Cherry'
        ' (leave the other two unchecked) and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Pick Fruits</title>
<style>body{font-family:sans-serif;margin:40px;font-size:22px}
label{display:block;margin:12px 0}
button{font-size:24px;padding:10px 30px;margin-top:20px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<label><input type="checkbox" id="c0"/> Apple</label>
<label><input type="checkbox" id="c1"/> Date</label>
<label><input type="checkbox" id="c2"/> Banana</label>
<label><input type="checkbox" id="c3"/> Eggplant</label>
<label><input type="checkbox" id="c4"/> Cherry</label>
<button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const want=[true,false,true,false,true];
  const ok=want.every((w,i)=>document.getElementById('c'+i).checked===w);
  document.getElementById('msg').innerText = ok?'Success!':'Try again';
}
</script></body></html>
"""


# =============================================================================
# 4. BrowserRadioPick — pick the "Yes" radio
# =============================================================================
class BrowserRadioPick(BrowserTask):
  """Choose the Yes radio option and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then select the "Yes" radio button and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Pick Yes</title>
<style>body{font-family:sans-serif;margin:40px;font-size:22px}
label{display:block;margin:12px 0}
button{font-size:24px;padding:10px 30px;margin-top:20px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<label><input type="radio" name="r" value="yes"/> Yes</label>
<label><input type="radio" name="r" value="no"/> No</label>
<label><input type="radio" name="r" value="maybe"/> Maybe</label>
<label><input type="radio" name="r" value="skip"/> Skip</label>
<button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const sel=document.querySelector('input[name=r]:checked');
  document.getElementById('msg').innerText =
    (sel && sel.value==='yes')?'Success!':'Try again';
}
</script></body></html>
"""


# =============================================================================
# 5. BrowserToggleAll — turn on all 3 toggles
# =============================================================================
class BrowserToggleAll(BrowserTask):
  """Switch all three toggles to the On state."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then turn on all three toggle switches on the page.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Toggle All</title>
<style>body{font-family:sans-serif;margin:40px;font-size:22px}
.row{margin:18px 0}
button.t{font-size:22px;padding:10px 30px;background:#eee}
button.t.on{background:#4caf50;color:white}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div class="row">WiFi <button class="t" id="t0" onclick="flip(0)">Off</button></div>
<div class="row">Bluetooth <button class="t" id="t1" onclick="flip(1)">Off</button></div>
<div class="row">Location <button class="t" id="t2" onclick="flip(2)">Off</button></div>
<div class="msg" id="msg"></div>
<script>
const state=[false,false,false];
function flip(i){
  state[i]=!state[i];
  const b=document.getElementById('t'+i);
  b.innerText = state[i]?'On':'Off';
  b.classList.toggle('on', state[i]);
  if(state.every(x=>x)) document.getElementById('msg').innerText='Success!';
}
</script></body></html>
"""


# =============================================================================
# 6. BrowserPickColor — click the red button
# =============================================================================
class BrowserPickColor(BrowserTask):
  """Click the red button out of four coloured buttons."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then click the red button.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Pick Color</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
button{font-size:0;width:120px;height:120px;margin:10px;border:none;border-radius:12px}
.msg{font-size:32px;margin-top:30px}</style></head>
<body>
<button style="background:#2196f3" onclick="hit('blue')">B</button>
<button style="background:#4caf50" onclick="hit('green')">G</button>
<button style="background:#e53935" onclick="hit('red')">R</button>
<button style="background:#fbc02d" onclick="hit('yellow')">Y</button>
<div class="msg" id="msg"></div>
<script>
function hit(c){
  document.getElementById('msg').innerText = (c==='red')?'Success!':'Wrong';
}
</script></body></html>
"""


# =============================================================================
# 7. BrowserOrderClick — click 3 buttons in stated order
# =============================================================================
class BrowserOrderClick(BrowserTask):
  """Press three labelled buttons in the specified order."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then click the buttons in this order:'
        ' First, then Second, then Third.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Order</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:50px}
button{font-size:22px;padding:18px 36px;margin:12px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<button id="b1" onclick="press(1)">First</button>
<button id="b2" onclick="press(2)">Second</button>
<button id="b3" onclick="press(3)">Third</button>
<div class="msg" id="msg"></div>
<script>
let step=1;
function press(n){
  if(n!==step){
    document.getElementById('msg').innerText='Try again';
    step=1;
    return;
  }
  step++;
  if(step>3) document.getElementById('msg').innerText='Success!';
}
</script></body></html>
"""


# =============================================================================
# 8. BrowserDropdown — pick Banana from a select
# =============================================================================
class BrowserDropdown(BrowserTask):
  """Choose Banana from a dropdown menu and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then open the dropdown, choose "Banana", and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Dropdown</title>
<style>body{font-family:sans-serif;margin:40px;font-size:22px}
select{font-size:22px;padding:6px;width:80%}
button{font-size:24px;padding:10px 30px;margin-top:20px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<select id="s">
  <option value="apple">Apple</option>
  <option value="banana">Banana</option>
  <option value="cherry">Cherry</option>
  <option value="date">Date</option>
</select>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const v=document.getElementById('s').value;
  document.getElementById('msg').innerText = (v==='banana')?'Success!':'Try again';
}
</script></body></html>
"""


# =============================================================================
# 9. BrowserSlider — drag slider to a target value
# =============================================================================
class BrowserSlider(BrowserTask):
  """Drag the slider to a target value (50) and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then move the slider to value 50 and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Slider</title>
<style>body{font-family:sans-serif;text-align:center;margin-top:50px}
input[type=range]{width:80%}
.val{font-size:36px;margin:20px}
button{font-size:22px;padding:10px 28px;margin-top:14px}
.msg{font-size:28px;margin-top:24px}</style></head>
<body>
<div class="val" id="v">0</div>
<input type="range" id="r" min="0" max="100" value="0"
       oninput="document.getElementById('v').innerText=this.value"/>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const v=parseInt(document.getElementById('r').value,10);
  document.getElementById('msg').innerText =
    (Math.abs(v-50)<=2)?'Success!':'Currently '+v;
}
</script></body></html>
"""


# =============================================================================
# 10. BrowserClickLargest — pick the largest button
# =============================================================================
class BrowserClickLargest(BrowserTask):
  """Click the largest of three differently-sized buttons."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then click the largest button on the page.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Largest</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:40px}
.b{display:inline-block;margin:14px;cursor:pointer;font-size:22px;background:#90caf9;border:none;color:white}
.s{width:70px;height:70px}
.m{width:130px;height:130px}
.l{width:200px;height:200px}
.msg{font-size:28px;margin-top:24px}</style></head>
<body>
<button class="b s" onclick="hit('s')">Small</button>
<button class="b m" onclick="hit('m')">Medium</button>
<button class="b l" onclick="hit('l')">Large</button>
<div class="msg" id="msg"></div>
<script>
function hit(c){
  document.getElementById('msg').innerText = (c==='l')?'Success!':'Wrong';
}
</script></body></html>
"""


# =============================================================================
# 11. BrowserDismissCards — close 3 cards via X button
# =============================================================================
class BrowserDismissCards(BrowserTask):
  """Dismiss all three cards by tapping their ✕ close icons."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then dismiss every card on the page by clicking its ✕ icon.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Dismiss</title>
<style>body{font-family:sans-serif;margin:30px}
.card{position:relative;background:#fff8e1;border:1px solid #ddd;
      padding:24px;margin:14px 0;font-size:22px;border-radius:8px}
.x{position:absolute;top:6px;right:10px;font-size:28px;cursor:pointer;color:#666}
.msg{font-size:28px;margin-top:20px}</style></head>
<body>
<div class="card" id="c0">Card A<span class="x" onclick="kill(0)">✕</span></div>
<div class="card" id="c1">Card B<span class="x" onclick="kill(1)">✕</span></div>
<div class="card" id="c2">Card C<span class="x" onclick="kill(2)">✕</span></div>
<div class="msg" id="msg"></div>
<script>
let left=3;
function kill(i){
  const c=document.getElementById('c'+i);
  if(!c) return;
  c.remove();
  left--;
  if(left===0) document.getElementById('msg').innerText='Success!';
}
</script></body></html>
"""


# =============================================================================
# 12. BrowserPickEven — click any even number
# =============================================================================
class BrowserPickEven(BrowserTask):
  """Click any even number out of six buttons."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then click any one button showing an even number.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Even</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:40px}
button{font-size:32px;padding:14px 28px;margin:8px}
.msg{font-size:28px;margin-top:24px}</style></head>
<body>
<button onclick="hit(1)">1</button>
<button onclick="hit(2)">2</button>
<button onclick="hit(3)">3</button>
<button onclick="hit(4)">4</button>
<button onclick="hit(5)">5</button>
<button onclick="hit(6)">6</button>
<div class="msg" id="msg"></div>
<script>
function hit(n){
  document.getElementById('msg').innerText =
    (n%2===0)?'Success!':('That is odd');
}
</script></body></html>
"""


# =============================================================================
# 13. BrowserCopyCode — copy a 4-digit code shown above into a field
# =============================================================================
class BrowserCopyCode(BrowserTask):
  """Read a 4-digit code on screen, type it into the field and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then read the 4-digit code shown on the page, type it into the'
        ' input box and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Code</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:50px}
.code{font-size:48px;letter-spacing:8px;font-weight:bold;margin:20px;
      padding:12px 24px;background:#eef;display:inline-block}
input{font-size:28px;padding:8px;width:50%;text-align:center}
button{font-size:24px;padding:10px 30px;margin-top:18px}
.msg{font-size:28px;margin-top:24px}</style></head>
<body>
<div>Your verification code:</div>
<div class="code" id="code"></div>
<input id="inp" placeholder="Enter code"/>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
const c=((%%SEED%% % 9000)+1000).toString();
document.getElementById('code').innerText=c;
function check(){
  const v=document.getElementById('inp').value.trim();
  document.getElementById('msg').innerText=(v===c)?'Success!':'Wrong';
}
</script></body></html>
"""


# =============================================================================
# 14. BrowserSum — basic single-digit addition
# =============================================================================
class BrowserSum(BrowserTask):
  """Solve a single-digit addition and submit the answer."""

  @property
  def goal(self) -> str:
    s = self.params['browser_task_seed']
    a = (s % 9) + 1
    b = ((s // 9) % 9) + 1
    return (
        self.preamble
        + f' Then read the question on the page, type the answer to {a}+{b}'
        ' in the input box, and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Sum</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:50px}
.q{font-size:42px;margin:20px}
input{font-size:28px;padding:8px;width:30%;text-align:center}
button{font-size:24px;padding:10px 30px;margin-top:18px}
.msg{font-size:28px;margin-top:24px}</style></head>
<body>
<div class="q" id="q"></div>
<input id="inp" type="number"/>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
const s=%%SEED%%;
const a=(s % 9)+1;
const b=(Math.floor(s/9) % 9)+1;
document.getElementById('q').innerText=a+' + '+b+' = ?';
function check(){
  const v=parseInt(document.getElementById('inp').value,10);
  document.getElementById('msg').innerText=(v===a+b)?'Success!':'Wrong';
}
</script></body></html>
"""


# =============================================================================
# 15. BrowserMatchColor — click two same-coloured boxes
# =============================================================================
class BrowserMatchColor(BrowserTask):
  """Find the two same-coloured boxes among four and click both."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then find the two boxes that share the same colour and click'
        ' both of them.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Match</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:40px}
.box{display:inline-block;width:120px;height:120px;margin:14px;
     border-radius:14px;cursor:pointer}
.picked{outline:6px solid #333}
.msg{font-size:28px;margin-top:20px}</style></head>
<body>
<div id="row"></div>
<div class="msg" id="msg"></div>
<script>
const colors=['#e91e63','#3f51b5','#e91e63','#ff9800'];
const seed=%%SEED%%;
function shuffle(a){
  let s=seed;
  for(let i=a.length-1;i>0;i--){
    s=(s*1103515245+12345)>>>0;
    const j=s%(i+1);
    [a[i],a[j]]=[a[j],a[i]];
  }
}
shuffle(colors);
const picked=new Set();
const row=document.getElementById('row');
colors.forEach((c,i)=>{
  const d=document.createElement('div');
  d.className='box';
  d.style.background=c;
  d.onclick=()=>{
    if(picked.has(i)) return;
    picked.add(i);
    d.classList.add('picked');
    if(picked.size===2){
      const [x,y]=[...picked];
      if(colors[x]===colors[y])
        document.getElementById('msg').innerText='Success!';
      else
        document.getElementById('msg').innerText='Wrong';
    }
  };
  row.appendChild(d);
});
</script></body></html>
"""


# =============================================================================
# 16. BrowserHeartIcon — click the ❤ icon out of four
# =============================================================================
class BrowserHeartIcon(BrowserTask):
  """Click the heart (like) icon out of four action icons."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then click the ❤ icon to like this post.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Like</title>
<style>body{font-family:sans-serif;text-align:center;margin-top:50px}
.icons span{font-size:48px;margin:0 18px;cursor:pointer}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div>A new photo from your friend.</div>
<div class="icons">
<span onclick="hit('heart')">❤</span>
<span onclick="hit('chat')">💬</span>
<span onclick="hit('share')">↗</span>
<span onclick="hit('save')">★</span>
</div>
<div class="msg" id="msg"></div>
<script>
function hit(k){
  document.getElementById('msg').innerText=(k==='heart')?'Success!':'Wrong icon';
}
</script></body></html>
"""


# =============================================================================
# 17. BrowserAgreeTerms — check terms + Continue
# =============================================================================
class BrowserAgreeTerms(BrowserTask):
  """Tick the I agree checkbox, then press Continue."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then check the "I agree" box and click Continue.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Terms</title>
<style>body{font-family:sans-serif;margin:36px;font-size:22px}
.terms{height:160px;overflow:auto;border:1px solid #ccc;
       padding:10px;margin-bottom:18px;background:#fafafa}
label{display:block;margin:14px 0}
button{font-size:24px;padding:10px 30px}
.msg{font-size:28px;margin-top:24px}</style></head>
<body>
<div class="terms">
By using this service you agree to follow our policies. We may collect
non-personal data about your usage. The full terms are available on our
website. Please scroll through and acknowledge below.
</div>
<label><input type="checkbox" id="ok"/> I agree to the terms</label>
<button onclick="check()">Continue</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  document.getElementById('msg').innerText =
    document.getElementById('ok').checked ? 'Success!' : 'You must agree';
}
</script></body></html>
"""


# =============================================================================
# 18. BrowserUnsubscribe — click the small unsubscribe link
# =============================================================================
class BrowserUnsubscribe(BrowserTask):
  """Find the small Unsubscribe link near the page bottom and tap it."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then find and click the "Unsubscribe" link.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Newsletter</title>
<style>body{font-family:sans-serif;margin:36px;font-size:22px}
h2{margin-top:0}
.body{margin:18px 0;line-height:1.5}
.footer{margin-top:40px;font-size:13px;color:#888;text-align:center}
.footer a{color:#888;text-decoration:underline;cursor:pointer}
.msg{font-size:28px;margin-top:24px;text-align:center}</style></head>
<body>
<h2>Weekly Updates</h2>
<div class="body">Hello! Here are this week's product highlights from our team.
Check out the latest features and stay tuned for more.</div>
<div class="footer">
You received this email because you signed up.
<a onclick="hit()">Unsubscribe</a> | Privacy | Terms
</div>
<div class="msg" id="msg"></div>
<script>
function hit(){ document.getElementById('msg').innerText='Success!'; }
</script></body></html>
"""


# =============================================================================
# 19. BrowserSearch — type and search
# =============================================================================
class BrowserSearch(BrowserTask):
  """Type a query into a search box and submit."""

  _QUERIES = ('hello', 'pizza', 'weather', 'sunset', 'music', 'travel')

  @property
  def goal(self) -> str:
    q = self._QUERIES[self.params['browser_task_seed'] % len(self._QUERIES)]
    return (
        self.preamble
        + f' Then type "{q}" into the search box and click Search.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Search</title>
<style>body{font-family:sans-serif;text-align:center;margin-top:60px}
input{font-size:24px;padding:10px;width:60%}
button{font-size:24px;padding:10px 28px;margin-left:8px}
.msg{font-size:28px;margin-top:24px}</style></head>
<body>
<input id="q" placeholder="Search..."/><button onclick="go()">Search</button>
<div class="msg" id="msg"></div>
<script>
const queries=['hello','pizza','weather','sunset','music','travel'];
const target=queries[%%SEED%% % queries.length];
function go(){
  const v=document.getElementById('q').value.trim().toLowerCase();
  document.getElementById('msg').innerText=(v===target)?'Success!':'Try again';
}
</script></body></html>
"""


# =============================================================================
# 20. BrowserResetPassword — enter same password twice
# =============================================================================
class BrowserResetPassword(BrowserTask):
  """Enter a new password (any non-empty value) twice and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then type the same password into both the "New password" and'
        ' "Confirm password" fields, then click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Reset</title>
<style>body{font-family:sans-serif;margin:36px;font-size:22px}
label{display:block;margin:14px 0 4px}
input{font-size:22px;padding:8px;width:80%}
button{font-size:24px;padding:10px 30px;margin-top:18px}
.msg{font-size:28px;margin-top:24px}</style></head>
<body>
<label>New password</label><input id="p1" type="password"/>
<label>Confirm password</label><input id="p2" type="password"/>
<button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const a=document.getElementById('p1').value;
  const b=document.getElementById('p2').value;
  document.getElementById('msg').innerText =
    (a.length>0 && a===b) ? 'Success!' : 'Passwords must match';
}
</script></body></html>
"""
