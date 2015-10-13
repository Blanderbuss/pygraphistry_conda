'use strict';

var _ = require('underscore');

var DataframeMask = require('../js/DataframeMask');
//var Dataframe = require('../js/Dataframe');

describe('union', function () {
    it('handles empty masks', function () {
        expect(DataframeMask.unionOfTwoMasks([], [])).toEqual([]);
    });
    it('handles singletons', function () {
        expect(DataframeMask.unionOfTwoMasks([3], [4])).toEqual([3, 4]);
        expect(DataframeMask.unionOfTwoMasks([4], [3])).toEqual([3, 4]);
        expect(DataframeMask.unionOfTwoMasks([3], [3])).toEqual([3]);
    });
    it('handles disjoint masks', function () {
        expect(DataframeMask.unionOfTwoMasks([3, 7], [2, 5])).toEqual([2, 3, 5, 7]);
        expect(DataframeMask.unionOfTwoMasks([], [2, 5])).toEqual([2, 5]);
    });
});

describe('intersection', function () {
    it('handles empty masks', function () {
        expect(DataframeMask.intersectionOfTwoMasks([], [])).toEqual([]);
    });
    it('handles singletons', function () {
        expect(DataframeMask.intersectionOfTwoMasks([3], [4])).toEqual([]);
        expect(DataframeMask.intersectionOfTwoMasks([4], [3])).toEqual([]);
        expect(DataframeMask.intersectionOfTwoMasks([3], [3])).toEqual([3]);
    });
    it('handles disjoint masks', function () {
        expect(DataframeMask.intersectionOfTwoMasks([3, 7], [2, 5])).toEqual([]);
        expect(DataframeMask.intersectionOfTwoMasks([], [2, 5])).toEqual([]);
    });
});

describe('complement', function () {
    it('handles empty masks', function () {
        expect(DataframeMask.complementOfMask([], 100)).toEqual(_.range(100));
    });
    it('handles singletons', function () {
        expect(DataframeMask.complementOfMask([3], 5)).toEqual([0,1,2,4]);
        expect(DataframeMask.complementOfMask([0], 5)).toEqual([1,2,3,4]);
        expect(DataframeMask.complementOfMask([5], 5)).toEqual([0,1,2,3,4]);
    });
    it('handles complex patterns', function () {
        expect(DataframeMask.complementOfMask([0,1,2,3,4], 5)).toEqual([]);
        expect(DataframeMask.complementOfMask([0,1], 5)).toEqual([2,3,4]);
        expect(DataframeMask.complementOfMask([0,4], 5)).toEqual([1,2,3]);
    });
    it('ignores elements outside the universe', function () {
        expect(DataframeMask.complementOfMask([6], 5)).toEqual([0,1,2,3,4]);
        expect(DataframeMask.complementOfMask([5], 5)).toEqual([0,1,2,3,4]);
        //expect(DataframeMask.complementOfMask([-1], 5)).toEqual([0,1,2,3,4]);
    });
});
