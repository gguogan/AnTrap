"""Tier F -- additional independent Chrome mini-games."""

from android_world.task_evals.single.browser import BrowserTask



class BrowserClick3(BrowserTask):
  """Click a single button exactly 3 times."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the big button 3 times.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Click 3</title>
<style>body{text-align:center;font-family:sans-serif}
button{font-size:32px;padding:24px 48px;margin-top:40px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div class="msg" id="msg">Clicks: 0</div>
<button onclick="tick()">Press me</button>
<script>
const target=3;
let n=0;
function tick(){
  n++;
  document.getElementById('msg').innerText =
    n>=target ? 'Success!' : 'Clicks: '+n;
}
</script></body></html>
"""


class BrowserClick4(BrowserTask):
  """Click a single button exactly 4 times."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the big button 4 times.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Click 4</title>
<style>body{text-align:center;font-family:sans-serif}
button{font-size:32px;padding:24px 48px;margin-top:40px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div class="msg" id="msg">Clicks: 0</div>
<button onclick="tick()">Press me</button>
<script>
const target=4;
let n=0;
function tick(){
  n++;
  document.getElementById('msg').innerText =
    n>=target ? 'Success!' : 'Clicks: '+n;
}
</script></body></html>
"""


class BrowserClick5(BrowserTask):
  """Click a single button exactly 5 times."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the big button 5 times.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Click 5</title>
<style>body{text-align:center;font-family:sans-serif}
button{font-size:32px;padding:24px 48px;margin-top:40px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div class="msg" id="msg">Clicks: 0</div>
<button onclick="tick()">Press me</button>
<script>
const target=5;
let n=0;
function tick(){
  n++;
  document.getElementById('msg').innerText =
    n>=target ? 'Success!' : 'Clicks: '+n;
}
</script></body></html>
"""


class BrowserClick6(BrowserTask):
  """Click a single button exactly 6 times."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the big button 6 times.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Click 6</title>
<style>body{text-align:center;font-family:sans-serif}
button{font-size:32px;padding:24px 48px;margin-top:40px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div class="msg" id="msg">Clicks: 0</div>
<button onclick="tick()">Press me</button>
<script>
const target=6;
let n=0;
function tick(){
  n++;
  document.getElementById('msg').innerText =
    n>=target ? 'Success!' : 'Clicks: '+n;
}
</script></body></html>
"""


class BrowserClick7(BrowserTask):
  """Click a single button exactly 7 times."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the big button 7 times.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Click 7</title>
<style>body{text-align:center;font-family:sans-serif}
button{font-size:32px;padding:24px 48px;margin-top:40px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div class="msg" id="msg">Clicks: 0</div>
<button onclick="tick()">Press me</button>
<script>
const target=7;
let n=0;
function tick(){
  n++;
  document.getElementById('msg').innerText =
    n>=target ? 'Success!' : 'Clicks: '+n;
}
</script></body></html>
"""


class BrowserClick8(BrowserTask):
  """Click a single button exactly 8 times."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the big button 8 times.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Click 8</title>
<style>body{text-align:center;font-family:sans-serif}
button{font-size:32px;padding:24px 48px;margin-top:40px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div class="msg" id="msg">Clicks: 0</div>
<button onclick="tick()">Press me</button>
<script>
const target=8;
let n=0;
function tick(){
  n++;
  document.getElementById('msg').innerText =
    n>=target ? 'Success!' : 'Clicks: '+n;
}
</script></body></html>
"""


class BrowserClick9(BrowserTask):
  """Click a single button exactly 9 times."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the big button 9 times.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Click 9</title>
<style>body{text-align:center;font-family:sans-serif}
button{font-size:32px;padding:24px 48px;margin-top:40px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div class="msg" id="msg">Clicks: 0</div>
<button onclick="tick()">Press me</button>
<script>
const target=9;
let n=0;
function tick(){
  n++;
  document.getElementById('msg').innerText =
    n>=target ? 'Success!' : 'Clicks: '+n;
}
</script></body></html>
"""


class BrowserClick10(BrowserTask):
  """Click a single button exactly 10 times."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the big button 10 times.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Click 10</title>
<style>body{text-align:center;font-family:sans-serif}
button{font-size:32px;padding:24px 48px;margin-top:40px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<div class="msg" id="msg">Clicks: 0</div>
<button onclick="tick()">Press me</button>
<script>
const target=10;
let n=0;
function tick(){
  n++;
  document.getElementById('msg').innerText =
    n>=target ? 'Success!' : 'Clicks: '+n;
}
</script></body></html>
"""


class BrowserPickBlue(BrowserTask):
  """Click the blue button out of six coloured buttons."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the blue button.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Pick blue</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
button{font-size:0;width:120px;height:120px;margin:10px;border:none;border-radius:12px}
.msg{font-size:32px;margin-top:30px}</style></head>
<body>
<button style="background:#2196f3" onclick="hit('blue')"></button>
<button style="background:#4caf50" onclick="hit('green')"></button>
<button style="background:#e53935" onclick="hit('red')"></button>
<button style="background:#fbc02d" onclick="hit('yellow')"></button>
<button style="background:#9c27b0" onclick="hit('purple')"></button>
<button style="background:#ff9800" onclick="hit('orange')"></button>
<button style="background:#e91e63" onclick="hit('pink')"></button>
<div class="msg" id="msg"></div>
<script>
function hit(c){
  document.getElementById('msg').innerText = (c==='blue')?'Success!':'Wrong';
}
</script></body></html>
"""


class BrowserPickGreen(BrowserTask):
  """Click the green button out of six coloured buttons."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the green button.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Pick green</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
button{font-size:0;width:120px;height:120px;margin:10px;border:none;border-radius:12px}
.msg{font-size:32px;margin-top:30px}</style></head>
<body>
<button style="background:#2196f3" onclick="hit('blue')"></button>
<button style="background:#4caf50" onclick="hit('green')"></button>
<button style="background:#e53935" onclick="hit('red')"></button>
<button style="background:#fbc02d" onclick="hit('yellow')"></button>
<button style="background:#9c27b0" onclick="hit('purple')"></button>
<button style="background:#ff9800" onclick="hit('orange')"></button>
<button style="background:#e91e63" onclick="hit('pink')"></button>
<div class="msg" id="msg"></div>
<script>
function hit(c){
  document.getElementById('msg').innerText = (c==='green')?'Success!':'Wrong';
}
</script></body></html>
"""


class BrowserPickYellow(BrowserTask):
  """Click the yellow button out of six coloured buttons."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the yellow button.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Pick yellow</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
button{font-size:0;width:120px;height:120px;margin:10px;border:none;border-radius:12px}
.msg{font-size:32px;margin-top:30px}</style></head>
<body>
<button style="background:#2196f3" onclick="hit('blue')"></button>
<button style="background:#4caf50" onclick="hit('green')"></button>
<button style="background:#e53935" onclick="hit('red')"></button>
<button style="background:#fbc02d" onclick="hit('yellow')"></button>
<button style="background:#9c27b0" onclick="hit('purple')"></button>
<button style="background:#ff9800" onclick="hit('orange')"></button>
<button style="background:#e91e63" onclick="hit('pink')"></button>
<div class="msg" id="msg"></div>
<script>
function hit(c){
  document.getElementById('msg').innerText = (c==='yellow')?'Success!':'Wrong';
}
</script></body></html>
"""


class BrowserPickPurple(BrowserTask):
  """Click the purple button out of six coloured buttons."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the purple button.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Pick purple</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
button{font-size:0;width:120px;height:120px;margin:10px;border:none;border-radius:12px}
.msg{font-size:32px;margin-top:30px}</style></head>
<body>
<button style="background:#2196f3" onclick="hit('blue')"></button>
<button style="background:#4caf50" onclick="hit('green')"></button>
<button style="background:#e53935" onclick="hit('red')"></button>
<button style="background:#fbc02d" onclick="hit('yellow')"></button>
<button style="background:#9c27b0" onclick="hit('purple')"></button>
<button style="background:#ff9800" onclick="hit('orange')"></button>
<button style="background:#e91e63" onclick="hit('pink')"></button>
<div class="msg" id="msg"></div>
<script>
function hit(c){
  document.getElementById('msg').innerText = (c==='purple')?'Success!':'Wrong';
}
</script></body></html>
"""


class BrowserPickOrange(BrowserTask):
  """Click the orange button out of six coloured buttons."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the orange button.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Pick orange</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
button{font-size:0;width:120px;height:120px;margin:10px;border:none;border-radius:12px}
.msg{font-size:32px;margin-top:30px}</style></head>
<body>
<button style="background:#2196f3" onclick="hit('blue')"></button>
<button style="background:#4caf50" onclick="hit('green')"></button>
<button style="background:#e53935" onclick="hit('red')"></button>
<button style="background:#fbc02d" onclick="hit('yellow')"></button>
<button style="background:#9c27b0" onclick="hit('purple')"></button>
<button style="background:#ff9800" onclick="hit('orange')"></button>
<button style="background:#e91e63" onclick="hit('pink')"></button>
<div class="msg" id="msg"></div>
<script>
function hit(c){
  document.getElementById('msg').innerText = (c==='orange')?'Success!':'Wrong';
}
</script></body></html>
"""


class BrowserPickPink(BrowserTask):
  """Click the pink button out of six coloured buttons."""

  @property
  def goal(self) -> str:
    return self.preamble + ' Then click the pink button.'

  HTML = """\
<!DOCTYPE html>
<html><head><title>Pick pink</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
button{font-size:0;width:120px;height:120px;margin:10px;border:none;border-radius:12px}
.msg{font-size:32px;margin-top:30px}</style></head>
<body>
<button style="background:#2196f3" onclick="hit('blue')"></button>
<button style="background:#4caf50" onclick="hit('green')"></button>
<button style="background:#e53935" onclick="hit('red')"></button>
<button style="background:#fbc02d" onclick="hit('yellow')"></button>
<button style="background:#9c27b0" onclick="hit('purple')"></button>
<button style="background:#ff9800" onclick="hit('orange')"></button>
<button style="background:#e91e63" onclick="hit('pink')"></button>
<div class="msg" id="msg"></div>
<script>
function hit(c){
  document.getElementById('msg').innerText = (c==='pink')?'Success!':'Wrong';
}
</script></body></html>
"""


class BrowserFillBob(BrowserTask):
  """Type the name Bob into an input and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then type the name "Bob" into the input field and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Fill Bob</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
input{font-size:24px;padding:8px;width:60%}
button{font-size:24px;padding:10px 30px;margin-top:20px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<input id="name" type="text" placeholder="Your name"/>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const v=document.getElementById('name').value.trim();
  document.getElementById('msg').innerText = (v==='Bob')?'Success!':'Try again';
}
</script></body></html>
"""


class BrowserFillCharlie(BrowserTask):
  """Type the name Charlie into an input and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then type the name "Charlie" into the input field and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Fill Charlie</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
input{font-size:24px;padding:8px;width:60%}
button{font-size:24px;padding:10px 30px;margin-top:20px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<input id="name" type="text" placeholder="Your name"/>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const v=document.getElementById('name').value.trim();
  document.getElementById('msg').innerText = (v==='Charlie')?'Success!':'Try again';
}
</script></body></html>
"""


class BrowserFillDiana(BrowserTask):
  """Type the name Diana into an input and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then type the name "Diana" into the input field and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Fill Diana</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
input{font-size:24px;padding:8px;width:60%}
button{font-size:24px;padding:10px 30px;margin-top:20px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<input id="name" type="text" placeholder="Your name"/>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const v=document.getElementById('name').value.trim();
  document.getElementById('msg').innerText = (v==='Diana')?'Success!':'Try again';
}
</script></body></html>
"""


class BrowserFillEdward(BrowserTask):
  """Type the name Edward into an input and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then type the name "Edward" into the input field and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Fill Edward</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
input{font-size:24px;padding:8px;width:60%}
button{font-size:24px;padding:10px 30px;margin-top:20px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<input id="name" type="text" placeholder="Your name"/>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const v=document.getElementById('name').value.trim();
  document.getElementById('msg').innerText = (v==='Edward')?'Success!':'Try again';
}
</script></body></html>
"""


class BrowserFillFiona(BrowserTask):
  """Type the name Fiona into an input and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then type the name "Fiona" into the input field and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Fill Fiona</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
input{font-size:24px;padding:8px;width:60%}
button{font-size:24px;padding:10px 30px;margin-top:20px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<input id="name" type="text" placeholder="Your name"/>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const v=document.getElementById('name').value.trim();
  document.getElementById('msg').innerText = (v==='Fiona')?'Success!':'Try again';
}
</script></body></html>
"""


class BrowserFillGrace(BrowserTask):
  """Type the name Grace into an input and submit."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then type the name "Grace" into the input field and click Submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html><head><title>Fill Grace</title>
<style>body{text-align:center;font-family:sans-serif;margin-top:60px}
input{font-size:24px;padding:8px;width:60%}
button{font-size:24px;padding:10px 30px;margin-top:20px}
.msg{font-size:28px;margin-top:30px}</style></head>
<body>
<input id="name" type="text" placeholder="Your name"/>
<br><button onclick="check()">Submit</button>
<div class="msg" id="msg"></div>
<script>
function check(){
  const v=document.getElementById('name').value.trim();
  document.getElementById('msg').innerText = (v==='Grace')?'Success!':'Try again';
}
</script></body></html>
"""
