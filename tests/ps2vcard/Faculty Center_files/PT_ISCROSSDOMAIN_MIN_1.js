




function isCrossDomain(objFrame)
{
if (!objFrame) return false;if (typeof(objFrame.document)!="object")
 return true;var props = objFrame.document.props;if (typeof(props) != "object")
 return true;if (props.domain != document.domain)
 return true;return false;}

function isCrossDomainTop() 
{
var objFrame;for (var j=0;j<top.frames.length;j++)
{
 objFrame = top.frames[j]; if (isCrossDomain(objFrame))
 return true; if (objFrame.frames)
 {
 for (var k=0;k<objFrame.frames.length;k++)
 {
 if (isCrossDomain(objFrame.frames[k]))
 return true; }
 }
}
return false;}