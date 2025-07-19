
(function (jQuery) {
    console.log('jquery.invoice.js');
    $.opt = {};  // jQuery Object

    jQuery.fn.invoice = function (options) {
        var ops = jQuery.extend({}, jQuery.fn.invoice.defaults, options);
        $.opt = ops;

        var inv = new Invoice();
        inv.init();

        jQuery('body').on('click', function (e) {
            
            inv.init();
        });

        jQuery('body').on('keyup', function (e) {
            inv.init();
        });

        return this;
    };
}(jQuery));

function Invoice() {
    self = this;
}

Invoice.prototype = {
    constructor: Invoice,

    init: function () {
        this.calcTotal();
        this.calcTotalQty();
        this.calcSubtotal();
        this.calcGrandTotal();
//        this.calcPaidAmount();
        this.calcRemainingAmount();
        this.calcReturnedAmount();
    },

    /**
     * Calculate total price of an item.
     *
     * @returns {number}
     */
    calcTotal: function () {
         jQuery($.opt.parentClass).each(function (i) {
             var row = jQuery(this);
             // here are the constitions of the invoice
             stock=Number(row.find('.stock').text())

             if ($(".createinvoice").length > 0) {
                // if(stock > 0){
                //     if(row.find($.opt.qty).val()>stock){
                //             row.find($.opt.qty).css('border-color', 'red');
                //             row.find($.opt.qty).val(Number(row.find('.stock').text()));
                //     }else {
                //             row.find($.opt.qty).css('border-color', 'gray');
                //     }
                // }
                var min = parseFloat(row.find($.opt.price).attr('min'));
                row.find($.opt.price).on('keyup', function () {
                    console.log('editing price')
                    priceerror=$(this).parent().find('.errorprice')
                    if ($(this).val() == min) {
                        $(this).parent().parent().addClass('pricenet');
                        priceerror.addClass('d-none');
                    } else if ($(this).val() < min) {
                        $(this).parent().parent().removeClass('pricenet');
                        $(this).css('border-color', 'red');
                        priceerror.removeClass('d-none');
                    }else{
                        $(this).parent().parent().removeClass('pricenet');
                        priceerror.addClass('d-none');
                        $(this).css('border-color', 'gray');
                    }
                })
                // if (row.find($.opt.price).val().length >= 3){
                //     if (row.find($.opt.price).val() >= 2) {
                //     row.find($.opt.price).css('border-color', 'red');
                //     alert('Prix de vent doit etre superieur ou egal a prix net: '+min+'')
                // } else {
                //     row.find($.opt.price).css('border-color', 'gray');
                // }}
            }
             var item_sub_price = row.find($.opt.price).val() * row.find($.opt.qty).val();

             // Uncomment when you want to use
             // var percent_discount = (item_sub_price * row.find($.opt.perdiscount).val())/100;
             //var total = item_sub_price - percent_discount;

             var total = row.find($.opt.price).val() * row.find($.opt.qty).val();

             total = self.roundNumber(total, 2);
             row.find($.opt.total).html(total);
         });

         return 1;
     },
	
    /***
     * Calculate total quantity of an order.
     *
     * @returns {number}
     */
    calcTotalQty: function () {
         var totalQty = 0;
         jQuery($.opt.qty).each(function (i) {
             var qty = jQuery(this).val();
             if (!isNaN(qty)) totalQty += Number(qty);
         });

         totalQty = self.roundNumber(totalQty, 2);

         jQuery($.opt.totalQty).html(totalQty);

         return 1;
     },

    /***
     * Calculate subtotal of an order.
     *
     * @returns {number}
     */
    calcSubtotal: function () {
         var subtotal = 0;
         jQuery($.opt.total).each(function (i) {
             var total = jQuery(this).html();
             if (!isNaN(total)) subtotal += Number(total);
         });

         subtotal = self.roundNumber(subtotal, 2);

         jQuery($.opt.subtotal).html(subtotal);

         return 1;
     },

    /**
     * Calculate grand total of an order.
     *
     * @returns {number}
     */
    calcGrandTotal: function () {
        var grandTotal = Number(jQuery($.opt.subtotal).html())
                       + Number(jQuery($.opt.shipping).val())
                       - Number(jQuery($.opt.discount).val());
        grandTotal = self.roundNumber(grandTotal, 2);

        jQuery($.opt.grandTotal).html(grandTotal);
        return 1;
    },

//    calcPaidAmount: function () {
//        var grandTotal = Number(jQuery($.opt.subtotal).html())
//                       + Number(jQuery($.opt.shipping).val())
//                       - Number(jQuery($.opt.discount).val());
//        grandTotal = self.roundNumber(grandTotal, 2);
//        jQuery($.opt.paidAmount).val(grandTotal);
//        return 1;
//    },
    
    calcRemainingAmount: function () {
        var remainingAmount = (Number(jQuery($.opt.grandTotal).html())
                       - Number(jQuery($.opt.paidAmount).val())).toFixed(2);
        jQuery($.opt.remainingAmount).html(remainingAmount);
        return 1;
    },

    calcReturnedAmount: function () {
        var returnedAmount = Number(jQuery($.opt.cashPayment).val())
            - Number(jQuery($.opt.grandTotal).html());
        jQuery($.opt.returnedCash).html(returnedAmount);
        return 1;
    },

    /**
     * Add a row.
     *
     * @returns {number}
     */
    newRow: function () {
        // Uncomment after re using that
        // var percent_discount = '<td><select class="form-control perdiscount" id="sel1"><option>0</option><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option><option>6</option><option>7</option><option>8</option><option>9</option><option>10</option></select></td>';

        
        return 1;
    },

    /**
     * Delete a row.
     *
     * @param elem   current element
     * @returns {number}
     */
    deleteRow: function (elem) {
        jQuery(elem).parents($.opt.parentClass).remove();

        if (jQuery($.opt.delete).length < 2) {
            jQuery($.opt.delete).hide();
        }

        return 1;
    },

    /**
     * Round a number.
     * Using: http://www.mediacollege.com/internet/javascript/number/round.html
     *
     * @param number
     * @param decimals
     * @returns {*}
     */
    roundNumber: function (number, decimals) {
        var newString;// The new rounded number
        decimals = Number(decimals);

        if (decimals < 1) {
            newString = (Math.round(number)).toString();
        } else {
            var numString = number.toString();

            if (numString.lastIndexOf(".") == -1) {// If there is no decimal point
                numString += ".";// give it one at the end
            }

            var cutoff = numString.lastIndexOf(".") + decimals;// The point at which to truncate the number
            var d1 = Number(numString.substring(cutoff, cutoff + 1));// The value of the last decimal place that we'll end up with
            var d2 = Number(numString.substring(cutoff + 1, cutoff + 2));// The next decimal, after the last one we want

            if (d2 >= 5) {// Do we need to round up at all? If not, the string will just be truncated
                if (d1 == 9 && cutoff > 0) {// If the last digit is 9, find a new cutoff point
                    while (cutoff > 0 && (d1 == 9 || isNaN(d1))) {
                        if (d1 != ".") {
                            cutoff -= 1;
                            d1 = Number(numString.substring(cutoff, cutoff + 1));
                        } else {
                            cutoff -= 1;
                        }
                    }
                }

                d1 += 1;
            }

            if (d1 == 10) {
                numString = numString.substring(0, numString.lastIndexOf("."));
                var roundedNum = Number(numString) + 1;
                newString = roundedNum.toString() + '.';
            } else {
                newString = numString.substring(0, cutoff) + d1.toString();
            }
        }

        if (newString.lastIndexOf(".") == -1) {// Do this again, to the new string
            newString += ".";
        }

        var decs = (newString.substring(newString.lastIndexOf(".") + 1)).length;

        for (var i = 0; i < decimals - decs; i++)
            newString += "0";
        //var newNumber = Number(newString);// make it a number if you like

        return newString; // Output the result to the form field (change for your purposes)
    }
};

/**
 *  Publicly accessible defaults.
 */
jQuery.fn.invoice.defaults = {
    addRow: "#addRow",
    delete: ".delete",
    parentClass: ".item-row",

    price: ".price",
    qty: ".qty",
    total: ".total",
    totalQty: "#totalQty",
    // perdiscount: '.perdiscount',

    subtotal: "#subtotal",
    discount: "#discount",
    shipping: "#shipping",
    grandTotal: "#grandTotal",

    remainingAmount: '#remainingAmount',
    paidAmount: '#paidAmount',

    cashPayment: '#cash_payment',
    returnedCash: '#returned_cash',
};