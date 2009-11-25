<script type="text/javascript">
	function setFlashImageId(param){
		document.getElementById("id_{{name}}").value += "\n" + param;
	}
</script>
{{ textfield }}<br />
<object classid="clsid:d27cdb6e-ae6d-11cf-96b8-444553540000" codebase="http://download.macromedia.com/pub/shockwave/cabs/flash/swflash.cab#version=10,0,0,0" width="250" height="125" id="uploader" align="middle">
	<param name="allowScriptAccess" value="sameDomain" />
	<param name="allowFullScreen" value="false" />
	<param name="movie" value="/media/uploader.swf" /><param name="quality" value="high" />
	<param name="bgcolor" value="#ffffff" />	
	<embed src="/media/uploader.swf" quality="high" bgcolor="#ffffff" width="250" height="125" name="uploader" align="middle" allowScriptAccess="sameDomain" allowFullScreen="false" type="application/x-shockwave-flash" pluginspage="http://www.adobe.com/go/getflashplayer" />
</object>