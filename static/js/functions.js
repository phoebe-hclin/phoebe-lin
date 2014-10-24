// remap jQuery to $
(function($){})(window.jQuery);


/* trigger when page is ready */
$(document).ready(function (){

	function change_header_bar() {
		var distance = $('#blog-wrap').offset().top - $('header').height();
		if ( $(window).scrollTop() >= distance ) {
			$('header').css('background-color','#383838');
		}
		else {
			$('header').css('background-color','');
		}
	}
	$(window).scroll(function() {
		change_header_bar();
	});
	$('#back-to-blog').click(function() {
		document.location.href = "/blog";
	});

    $('.blogfront .content').each(function(i){
    	if ($(this).height() > 305) {
    		$(this).css({'max-height': '305px', 'overflow': 'hidden'});
			$(this).next('.more-content').css('display', 'block');
    	}
    });
    
    var width = window.innerWidth || document.documentElement.clientWidth;
    if (width > 480) {
    
    	$('.blogfront .content > img')
    		.addClass('grayscale-img')
			.mouseover(function(){
				$(this).removeClass('grayscale-img');
			})
			.mouseout(function(){
				$(this).addClass('grayscale-img');
			});
		$('.single-post .content > img')
			.click(function(i){
				if ( $(this).width() == $(this).parent().width() ){
					var newElem = $(this).next();
					if (newElem.hasClass('photo-gallery'))
					{
						newElem.removeClass('hide');
						newElem.addClass('show');
					}
					else
					{
						newElem = $("<div class='photo-gallery transparentbg-black show'>")
						.append($(this).clone())
						.insertAfter(this)
						.click(function(){
							$(this).removeClass('show');
							$(this).addClass('hide');
						});
					}
				}
			});
    }

});