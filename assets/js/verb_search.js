(function($, undefined){
    var categorySelect = $("#categorySelect");
    var verbSelect = $("#verbSelect");
    var tagSelect = $("#tagSelect");
    var url = "/api/contenus/verbs/";
    var itemUrl = "/api/contenus/items/";
    var listOfContentContainer = $("#contentList");
    var appendCategory = function (url) {
        if(categorySelect.val() === ""){
            return url;
        }
        else{
            return url + "?category=" + categorySelect.val();
        }
    };
    var appendVerb = function (url) {
        if(verbSelect.val() === ""){
            return url;
        }
        else{
            return (url.indexOf("?") > -1? url + "&verb=":url + "?verb=") + verbSelect.val();
        }
    };
    var updateListOfContentContainer = function (listOfContent) {
        listOfContentContainer.html("");
        $.each(listOfContent, function () {
            var content = this; // just because I always get messy with js this.
            listOfContentContainer.append($(content));
        });
    };
    var getFresherContentList = function () {
        $.ajax(appendVerb(appendCategory(itemUrl)), {dataType:"json", method:"GET"}).success(function (data) {
            updateListOfContentContainer(data);
        });
    };
    var updateVerbSelect = function (listOfVerb) {
        verbSelect.html("");
        $.each(listOfVerb, function () {
            $("<option/>").val(this).text(this).appendTo(verbSelect);
        });
    };
    categorySelect.on("change", function () {
        var url = appendCategory("/api/contenus/verbs/");
        $.ajax(url, {
            dataType:"json",
            "method": "get"
        }).success(function (data) {
            updateVerbSelect(data);

        });

    });
    verbSelect.on("change", function () {
        getFresherContentList();
    });
})(jQuery);
