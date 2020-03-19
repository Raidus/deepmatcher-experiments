import pandas as pd
import deepmatcher as dm
from itertools import chain, combinations
import numpy as np
import random as rd
import math
from tqdm import tqdm
from utils.deepmatcher_utils import wrapDm
from utils.sampleBuilder import buildNegativeFromSample
from strsimpy.normalized_levenshtein import NormalizedLevenshtein
from strsimpy.jaccard import Jaccard



##maxLenAttributes is the maximum number of perturbed attributes we want to consider
def aggregateRankings(ranking_l,positive,maxLenAttributes,lenTriangles):
    allRank = {}
    for rank in ranking_l:
        for key in rank.keys():
            if len(key) <= maxLenAttributes:
                if key in allRank:
                    allRank[key] += 1/lenTriangles
                else:
                    allRank[key] = 1/lenTriangles
    alteredAttr = list(map(lambda t:"/".join(t),list(allRank.keys())))
    rankForHistogram = {'attributes':alteredAttr,'flipped':list(allRank.values())}
    fig_height = len(alteredAttr)
    fig_width = fig_height
    df = pd.DataFrame(rankForHistogram)
    if positive:
        ax = df.plot.barh(x='attributes', y='flipped',color='green',figsize=(fig_height,fig_width))
    else:
        ax = df.plot.barh(x='attributes', y='flipped',color='red',figsize=(fig_height,fig_width))
    return ax,allRank


def _renameColumnsWithPrefix(prefix,df):
        newcol = []
        for col in list(df):
            newcol.append(prefix+col)
        df.columns = newcol

    
def _powerset(xs,minlen,maxlen):
    return [subset for i in range(minlen,maxlen+1)
            for subset in combinations(xs, i)]

    

def createPerturbationsFromTriangle(triangle,attributes,maxLenAttributeSet,originalClass):
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
    _renameColumnsWithPrefix('ltable_',r1_df)
    _renameColumnsWithPrefix('rtable_',perturbations_df)
    allPerturbations = pd.concat([r1_df,perturbations_df], axis=1)
    allPerturbations['id'] = np.arange(len(allPerturbations))
    allPerturbations['alteredAttributes'] = perturbedAttributes
    return allPerturbations,perturbedAttributes


    
def generateNewNegatives(df,source1,source2,newNegativesToBuild):
    allNewNegatives = []
    jaccard = Jaccard(3)
    positives = df[df.label==1]
    negatives = df[df.label==0]
    newNegativesPerSample = math.ceil(newNegativesToBuild/len(positives))
    for i in range(len(positives)):
        locc = np.count_nonzero(negatives.ltable_id.values==positives.iloc[i]['ltable_id'])
        rocc = np.count_nonzero(negatives.rtable_id.values == positives.iloc[i]['rtable_id'])
        if locc==0 and rocc == 0:
            permittedIds = [sampleid for sampleid in df['rtable_id'].values if sampleid!= df.iloc[i]['rtable_id']]
            newNegatives_l = buildNegativeFromSample(positives.iloc[i]['ltable_id'],permittedIds,\
                                                     newNegativesPerSample,source1,source2,jaccard,0.5)
            newNegatives_df = pd.DataFrame(data=newNegatives_l,columns=['ltable_id','rtable_id','label'])
            allNewNegatives.append(newNegatives_df)
    allNewNegatives_df = pd.concat(allNewNegatives)
    return allNewNegatives_df


def prepareDataset(dataset,source1,source2,newNegativesToBuild,left_prefix='ltable_',right_prefix='rtable_'):
    colForDrop = [col for col in list(dataset) if col not in ['id','ltable_id','rtable_id','label']]
    dataset = dataset.drop_duplicates(colForDrop)
    newNegatives = generateNewNegatives(dataset,source1,source2,newNegativesToBuild)
    left_columns = []
    right_columns = []
    source1_c = source1.copy()
    source2_c = source2.copy()
    for lcol,rcol in zip(list(source1_c),list(source2_c)):
        left_columns.append(left_prefix+lcol)
        right_columns.append(right_prefix+rcol)
    source1_c.columns = left_columns
    source2_c.columns = right_columns
    pdata = pd.merge(newNegatives,source1_c, how='inner')
    newNegatives_df = pd.merge(pdata,source2_c,how='inner')
    lastDataset_id = dataset['id'].values[-1]
    newNegatives_df['id'] = np.arange(lastDataset_id+1,lastDataset_id+1+len(newNegatives_df))
    augmentedData = pd.concat([dataset,newNegatives_df])
    return augmentedData



## for now we suppose to have only two sources
def getMixedTriangles(dataset,sources):
        triangles = []
        positives = dataset[dataset.label==1]
        negatives = dataset[dataset.label==0]
        l_pos_ids = positives.ltable_id.values
        r_pos_ids = positives.rtable_id.values
        for lid,rid in zip(l_pos_ids,r_pos_ids):
            if np.count_nonzero(negatives.rtable_id.values==rid) >=1:
                relatedTuples = negatives[negatives.rtable_id == rid]
                for curr_lid in relatedTuples.ltable_id.values:
                    triangles.append((sources[0].iloc[lid],sources[1].iloc[rid],sources[0].iloc[curr_lid]))
            if np.count_nonzero(negatives.ltable_id.values==lid)>=1:
                relatedTuples = negatives[negatives.ltable_id==lid]
                for curr_rid in relatedTuples.rtable_id.values:
                    triangles.append((sources[1].iloc[rid],sources[0].iloc[lid],sources[1].iloc[curr_rid]))
        return triangles
    

## not used for now
def getNegativeTriangles(dataset,sources):
        triangles = []
        negatives = dataset[dataset.label==0]
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
        positives = dataset[dataset.label==1]
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

    
def explainSamples(dataset,sources,model,originalClass,maxLenAttributeSet):
        ## we suppose that the sample is always on the left source
        attributes = [col for col in list(sources[0]) if col not in ['id']]
        allTriangles = getMixedTriangles(dataset,sources)
        rankings = []
        triangleIds = []
        flippedPredictions = []
        notFlipped = []
        for triangle in tqdm(allTriangles):
            triangleIds.append((triangle[0].id,triangle[1].id,triangle[2].id))
            currentPerturbations,currPerturbedAttr = createPerturbationsFromTriangle(triangle,attributes\
                                                                            ,maxLenAttributeSet,originalClass)
            predictions = wrapDm(currentPerturbations,model,\
                                  ignore_columns=['ltable_id','rtable_id','alteredAttributes'],batch_size=1)
            curr_flippedPredictions = currentPerturbations[(predictions[:,originalClass] <0.5)]
            currNotFlipped = currentPerturbations[(predictions[:,originalClass] >0.5)]
            notFlipped.append(currNotFlipped)
            flippedPredictions.append(curr_flippedPredictions)
            ranking = getAttributeRanking(predictions,currPerturbedAttr,originalClass)
            rankings.append(ranking)
        flippedPredictions_df = pd.concat(flippedPredictions,ignore_index=True)
        notFlipped_df = pd.concat(notFlipped,ignore_index=True)
        return rankings,triangleIds,flippedPredictions_df,notFlipped_df

    
##check if s1 is not superset of one element in s2list 
def _isNotSuperset(s1,s2_list):
    for s2 in s2_list:
        if set(s2).issubset(set(s1)):
            return False
    return True


def getAttributeRanking(proba,alteredAttributes,originalClass):
    attributeRanking = {}
    for i,prob in enumerate(proba):
        if prob[originalClass] <0.5:
            if _isNotSuperset(alteredAttributes[i],list(attributeRanking.keys())):
                attributeRanking[alteredAttributes[i]] = 1
    return attributeRanking
    