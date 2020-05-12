import pandas as pd
from itertools import chain, combinations
from collections import defaultdict
import numpy as np
import random as rd
import math
import string
import os
from tqdm import tqdm



def __getCorrectPredictions(dataset,model,predict_fn):
    predictions = predict_fn(dataset,model,['label','id'])
    tp_group = dataset[(predictions[:,1]>=0.5)& (dataset['label'] == 1)]
    tn_group = dataset[(predictions[:,0] >=0.5)& (dataset['label']==0)]
    correctPredictions = pd.concat([tp_group,tn_group])
    return correctPredictions

    

def _renameColumnsWithPrefix(prefix,df):
        newcol = []
        for col in list(df):
            newcol.append(prefix+col)
        df.columns = newcol

    
def _powerset(xs,minlen,maxlen):
    return [subset for i in range(minlen,maxlen+1)
            for subset in combinations(xs, i)]



## for now the code works only on binary sources
def getMixedTriangles(dataset,sources):
        triangles = []
        ##to not alter original dataset
        dataset_c = dataset.copy()
        dataset_c['ltable_id'] = list(map(lambda lrid:lrid.split("#")[0],dataset_c.id.values))
        dataset_c['rtable_id'] = list(map(lambda lrid:lrid.split("#")[1],dataset_c.id.values))
        positives = dataset_c[dataset_c.label==1]
        negatives = dataset_c[dataset_c.label==0]
        l_pos_ids = positives.ltable_id.values
        r_pos_ids = positives.rtable_id.values
        for lid,rid in zip(l_pos_ids,r_pos_ids):
            if np.count_nonzero(negatives.rtable_id.values==rid) >=1:
                relatedTuples = negatives[negatives.rtable_id == rid]
                for curr_lid in relatedTuples.ltable_id.values:
                    triangles.append((sources[0][sources[0].id==lid].iloc[0],\
                                      sources[1][sources[1].id==rid].iloc[0],\
                                      sources[0][sources[0].id==curr_lid].iloc[0],'L-R-L'))
            if np.count_nonzero(negatives.ltable_id.values==lid)>=1:
                relatedTuples = negatives[negatives.ltable_id==lid]
                for curr_rid in relatedTuples.rtable_id.values:
                    triangles.append((sources[1][sources[1].id==rid].iloc[0],\
                                      sources[0][sources[0].id==lid].iloc[0],\
                                      sources[1][sources[1].id==curr_rid].iloc[0],'R-L-R'))
        return triangles
    

    
def getNegativeTriangles(dataset,sources):
        triangles = []
        dataset_c = dataset.copy()
        dataset_c['ltable_id'] = list(map(lambda lrid:int(lrid.split("#")[0]),dataset_c.id.values))
        dataset_c['rtable_id'] = list(map(lambda lrid:int(lrid.split("#")[1]),dataset_c.id.values))
        negatives = dataset_c[dataset_c.label==0]
        l_neg_ids = negatives.ltable_id.values
        r_neg_ids = negatives.rtable_id.values
        for lid,rid in zip(l_neg_ids,r_neg_ids):
            if np.count_nonzero(r_neg_ids==rid)>=2:
                
                relatedTuples = negatives[negatives.rtable_id == rid]
                for curr_lid in relatedTuples.ltable_id.values:
                    if curr_lid!= lid:
                        triangles.append((sources[0].iloc[lid],sources[1].iloc[rid],sources[0].iloc[curr_lid]))
            if np.count_nonzero(l_neg_ids == lid) >=2:
                relatedTuples = negatives[negatives.ltable_id == lid]
                for curr_rid in relatedTuples.rtable_id.values:
                    if curr_rid != rid:
                        triangles.append((sources[1].iloc[rid],sources[0].iloc[lid],sources[1].iloc[curr_rid]))
        return triangles
    

def getPositiveTriangles(dataset,sources):
        triangles = []
        dataset_c = dataset.copy()
        dataset_c['ltable_id'] = list(map(lambda lrid:int(lrid.split("#")[0]),dataset_c.id.values))
        dataset_c['rtable_id'] = list(map(lambda lrid:int(lrid.split("#")[1]),dataset_c.id.values))
        positives = dataset_c[dataset_c.label==1]
        l_pos_ids = positives.ltable_id.values
        r_pos_ids = positives.rtable_id.values
        for lid,rid in zip(l_pos_ids,r_pos_ids):
            if np.count_nonzero(l_pos_ids==rid)>=2:
                relatedTuples = positives[positives.rtable_id == rid]
                for curr_lid in relatedTuples.ltable_id.values:
                    if curr_lid!= lid:
                        triangles.append((sources[0].iloc[lid],sources[1].iloc[rid],sources[0].iloc[curr_lid]))
            if np.count_nonzero(l_pos_ids == lid) >=2:
                relatedTuples = positives[positives.ltable_id == lid]
                for curr_rid in relatedTuples.rtable_id.values:
                    if curr_rid != rid:
                        triangles.append((sources[1].iloc[rid],sources[0].iloc[lid],sources[1].iloc[curr_rid]))
        return triangles

    
    
def createPerturbationsFromTriangle(triangle,attributes,maxLenAttributeSet,originalClass,
                                   lprefix='ltable_',rprefix='rtable_'):
    allAttributesSubsets = list(_powerset(attributes,1,maxLenAttributeSet))
    perturbations = []
    perturbedAttributes = []
    for subset in allAttributesSubsets:
        perturbedAttributes.append(subset)
        if originalClass==1:
            newRow = triangle[1].copy()
            for att in subset:
                newRow[att] = triangle[2][att]
            perturbations.append(newRow)
        else:
            newRow = triangle[2].copy()
            for att in subset:
                newRow[att] = triangle[1][att]
            perturbations.append(newRow)
    perturbations_df = pd.DataFrame(perturbations,index = np.arange(len(perturbations)))
    r1 = triangle[0]
    r1_copy = [r1]*len(perturbations_df)
    r1_df = pd.DataFrame(r1_copy, index=np.arange(len(perturbations)))
    _renameColumnsWithPrefix(lprefix,r1_df)
    _renameColumnsWithPrefix(rprefix,perturbations_df)
    allPerturbations = pd.concat([r1_df,perturbations_df], axis=1)
    allPerturbations = allPerturbations.drop([lprefix+'id',rprefix+'id'],axis=1)
    allPerturbations['alteredAttributes'] = perturbedAttributes
    return allPerturbations

    
    
def explainSamples(dataset:pd.DataFrame,sources:list,model,predict_fn:callable,
                   class_to_explain:int,maxLenAttributeSet:int):
        # we suppose that the sample is always on the left source
        attributes = [col for col in list(sources[0]) if col not in ['id']]
        allTriangles = getMixedTriangles(dataset,sources)
        rankings = []
        flippedPredictions = []
        #notFlipped = []
        for triangle in tqdm(allTriangles):
            currentPerturbations = createPerturbationsFromTriangle(triangle,attributes\
                                                                            ,maxLenAttributeSet,class_to_explain)
            currPerturbedAttr = currentPerturbations.alteredAttributes.values
            predictions = predict_fn(currentPerturbations,model,['alteredAttributes'])
            curr_flippedPredictions = currentPerturbations[(predictions[:,class_to_explain] <0.5)]
            '''
            currNotFlipped = currentPerturbations[(predictions[:,originalClass]>0.5)]
            notFlipped.append(currNotFlipped)
            '''
            flippedPredictions.append(curr_flippedPredictions)
            ranking = getAttributeRanking(predictions,currPerturbedAttr,class_to_explain)
            rankings.append(ranking)
        flippedPredictions_df = pd.concat(flippedPredictions,ignore_index=True)
        #notFlipped_df = pd.concat(notFlipped,ignore_index=True)
        aggregatedRankings = aggregateRankings(rankings,lenTriangles=len(allTriangles),maxLenAttributeSet=maxLenAttributeSet)
        return aggregatedRankings,flippedPredictions_df

    
#check if s1 is not superset of one element in s2list 
def _isNotSuperset(s1,s2_list):
    for s2 in s2_list:
        if set(s2).issubset(set(s1)):
            return False
    return True


def getAttributeRanking(proba:np.ndarray,alteredAttributes:list,originalClass:int):
    attributeRanking = {k:0 for k in alteredAttributes}
    for i,prob in enumerate(proba):
        if prob[originalClass] <0.5:
            attributeRanking[alteredAttributes[i]] = 1
    return attributeRanking


#MaxLenAttributeSet is the max len of perturbed attributes we want to consider
def aggregateRankings(ranking_l:list,lenTriangles:int,maxLenAttributeSet:int):
    aggregateRanking = defaultdict(int)
    for ranking in ranking_l:
        for altered_attr in ranking.keys():
            if len(altered_attr)<=maxLenAttributeSet:
                aggregateRanking[altered_attr] += ranking[altered_attr]
    aggregateRanking_normalized = {k:(v/lenTriangles) for (k,v) in aggregateRanking.items()}
    alteredAttr = list(map(lambda t:"/".join(t),aggregateRanking_normalized.keys()))
    return pd.Series(data=list(aggregateRanking_normalized.values()),index=alteredAttr)