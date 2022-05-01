# classes for converting a dataframe or Graphistry Plottable into a DGL
from typing import List, Any, Optional, TYPE_CHECKING, Union
import pandas as pd
from collections import Counter
import numpy as np

try:
    import dgl
    has_dependancy = True
except:
    has_dependancy = False

from . import constants as config
from .feature_utils import (
    FeatureEngine,
    FeatureMixin,
    resolve_feature_engine,
    XSymbolic,
    YSymbolic,
    resolve_X,
    resolve_y
)
from .util import setup_logger

logger = setup_logger(__name__, verbose=False)


if TYPE_CHECKING:
    MIXIN_BASE = FeatureMixin
else:
    MIXIN_BASE = object
    
    
# #########################################################################################
#
#  Torch helpers
#
# #########################################################################################


def convert_to_torch(X_enc: pd.DataFrame, y_enc: Optional[pd.DataFrame]):
    """
        Converts X, y to torch tensors compatible with ndata/edata of DGL graph
    _________________________________________________________________________
    :param X_enc: DataFrame Matrix of Values for Model Matrix
    :param y_enc: DataFrame Matrix of Values for Target
    :return: Dictionary of torch encoded arrays
    """
    import torch
    if not y_enc.empty:
        data = {
            config.FEATURE: torch.tensor(X_enc.values),
            config.TARGET: torch.tensor(y_enc.values),
        }
    else:
        data = {config.FEATURE: torch.tensor(X_enc.values)}
    return data




# #################################################################################################
#
#   DGL helpers
#
# #################################################################################################


def get_available_devices():
    """Get IDs of all available GPUs.

    Returns:
        device (torch.device): Main device (GPU 0 or CPU).
        gpu_ids (list): List of IDs of all GPUs that are available.
    """
    import torch
    gpu_ids = []
    if torch.cuda.is_available():
        gpu_ids += [gpu_id for gpu_id in range(torch.cuda.device_count())]
        device = torch.device(f"cuda:{gpu_ids[0]}")
        torch.cuda.set_device(device)
    else:
        device = torch.device("cpu")
    
    return device, gpu_ids


def reindex_edgelist(df, src, dst):
    """Since DGL needs integer contiguous node labels, this relabels as pre-processing step

    :eg
        df, ordered_nodes_dict = reindex_edgelist(df, 'to_node', 'from_node')
        creates new columns given by config.SRC and config.DST
    :param df: edge dataFrame
    :param src: source column of dataframe
    :param dst: destination column of dataframe

    :returns
        df, pandas DataFrame with new edges.
        ordered_nodes_dict, dict ordered from most common src and dst nodes.
    """
    srclist = df[src]
    dstlist = df[dst]
    cnt = Counter(
        pd.concat([srclist, dstlist], axis=0)
    )  # can also use pd.Factorize but doesn't order by count, which is satisfying
    ordered_nodes_dict = {k: i for i, (k, c) in enumerate(cnt.most_common())}
    df[config.SRC] = df[src].apply(lambda x: ordered_nodes_dict[x])
    df[config.DST] = df[dst].apply(lambda x: ordered_nodes_dict[x])
    return df, ordered_nodes_dict


def pandas_to_sparse_adjacency(df, src, dst, weight_col):
    """
        Takes a Pandas Dataframe and named src and dst columns into a sparse adjacency matrix in COO format
        Needed for DGL utils
    :param df: edges dataframe
    :param src: source column
    :param dst: destination column
    :param weight_col: optional weight column
    :return: COO sparse matrix, dictionary of src, dst nodes to index
    """
    # use scipy sparse to encode matrix
    from scipy.sparse import coo_matrix
    
    # have to reindex to align edge list with range(n_nodes) with new SRC and DST columns
    df, ordered_nodes_dict = reindex_edgelist(df, src, dst)
    
    eweight = np.array([1] * len(df))
    if weight_col is not None:
        eweight = df[weight_col].values
    
    shape = len(ordered_nodes_dict)
    sp_mat = coo_matrix(
        (eweight, (df[config.SRC], df[config.DST])), shape=(shape, shape)
    )
    return sp_mat, ordered_nodes_dict


# ##############################################################################

def pandas_to_dgl_graph(
    df: pd.DataFrame, src: str, dst: str, weight_col: str = None, device: str = "cpu"
):
    """Turns an edge DataFrame with named src and dst nodes, to DGL graph
    :eg
        g, sp_mat, ordered_nodes_dict = pandas_to_sparse_adjacency(df, 'to_node', 'from_node')
    :param df: DataFrame with source and destination and optionally weight column
    :param src: source column of DataFrame for coo matrix
    :param dst: destination column of DataFrame for coo matrix
    :param weight_col: optional weight column when constructing coo matrix
    :param device: whether to put dgl graph on cpu or gpu
    :return
        g: dgl graph
        sp_mat: sparse scipy matrix
        ordered_nodes_dict: dict ordered from most common src and dst nodes
    """
    sp_mat, ordered_nodes_dict = pandas_to_sparse_adjacency(df, src, dst, weight_col)

    g = dgl.from_scipy(sp_mat, device=device)  # there are other ways too
    logger.info(f"Graph Type: {type(g)}")  # why is this making a heterograph?

    return g, sp_mat, ordered_nodes_dict


def get_torch_train_test_mask(n: int, ratio: float = 0.8):
    """
        Generates random torch tensor mask
    :param n: size of mask
    :param ratio: mimics train/test split. `ratio` sets number of True vs False mask entries.
    :return: train and test torch tensor masks
    """
    import torch

    train_mask = torch.zeros(n, dtype=torch.bool).bernoulli(ratio)
    test_mask = ~train_mask
    return train_mask, test_mask

########################################################################################################################
#
#   DGL MIXIN
#
#######################################################################################################################

class DGLGraphMixin(MIXIN_BASE):
    """
        Automagic DGL models from Graphistry Instances.
        
    """
    def __init__(
        self,
    ):
        """
        :param train_split: split percent between train and test, set in mask on dgl edata/ndata
        :param device: Whether to put on cpu or gpu. Can always envoke .to(gpu) on returned DGL graph later, Default 'cpu'
        """

        self.dgl_initialized = False


    def dgl_lazy_init(self, train_split: float = 0.8, device: str = "cpu"):
        """
        Initialize DGL graph lazily
        :return:
        """

        if not self.dgl_initialized:

            self.train_split = train_split
            self.device = device
            self._removed_edges_previously = False
            self.DGL_graph = None

            self.dgl_initialized = True


    def _prune_edge_target(self):
        if self._edge_target is not None and hasattr(self, "_MASK"):
            self._edge_target = self._edge_target[self._MASK]


    def _remove_edges_not_in_nodes(self, node_column: str):
        # need to do this so we get the correct ndata size ...
        
        nodes = self._nodes[node_column]
        if not isinstance(self._edges, pd.DataFrame):  # type: ignore
            raise ValueError("self._edges for DGLGraphMix must be pd.DataFrame, recieved: %s", type(self._edges))  # type: ignore
        edf : pd.DataFrame = self._edges  # type: ignore
        n_initial = len(edf)
        logger.info(f"Length of edge DataFrame {n_initial}")
        
        mask = edf[self._source].isin(nodes) & edf[self._destination].isin(nodes)
        assert sum(mask) > 2, f'mask slice is (practically) empty, will lead to bad graph, found {sum(mask)}'
        self._MASK = mask
        self._edges = edf[mask]
        self._prune_edge_target()
        n_final = len(self._edges)
        logger.info(f"Length of edge DataFrame {n_final} after pruning")
        n_final = len(self._edges)
        if n_final != n_initial:
            logger.warn(
                "** Original Edge DataFrame has been changed, some elements have been dropped **"
            )
        self._removed_edges_previously = True


    def _check_nodes_lineup_with_edges(self):
        node_column = self._node
        nodes = self._nodes[node_column]
        unique_nodes = nodes.unique()
        logger.info(
            f"{len(nodes)} entities from column {node_column}\n with {len(unique_nodes)} unique entities"
        )
        if len(nodes) != len(
            unique_nodes
        ):  # why would this be so? Oh might be so for logs data...oof
            logger.warning(
                f"Nodes DataFrame has duplicate entries for column {node_column}"
            )
        # now check that self._entity_to_index is in 1-1 to with self.ndf[node_column]
        nodes = self._nodes[node_column]
        res = nodes.isin(self._entity_to_index)
        if res.sum() != len(nodes):
            logger.warning(
                "Some Edges connect to Nodes not explicitly mentioned in nodes DataFrame (ndf)"
            )
        if len(self._entity_to_index) > len(nodes):
            logger.warning(
                "There are more entities in edges DataFrame (edf) than in nodes DataFrame (ndf)"
            )


    def _convert_edge_dataframe_to_DGL(self, weight_column: Optional[str] = None, inplace: bool = False):
        logger.info("converting edge DataFrame to DGL graph")
        
        if inplace:
            res = self
        else:
            res = self.bind()
  
        if res._node is None:
            res._node = config.IMPLICIT_NODE_ID

        if not res._removed_edges_previously:
            logger.info(f'---------------- Node in convert dataframe to dgl: {res._node}')
            res._remove_edges_not_in_nodes(res._node)

        if res._source is None:
            raise ValueError('source column not set, try running g.bind(source="my_col") or g.edges(df, source="my_col")')

        if res._destination is None:
            raise ValueError('destination column not set, try running g.bind(destination="my_col") or g.edges(df, destination="my_col")')

        res.DGL_graph, res._adjacency, res._entity_to_index = pandas_to_dgl_graph(
            res._edges,
            res._source,
            res._destination,
            weight_col=weight_column,
            device=res.device,
        )
        res._index_to_entity = {k: v for v, k in res._entity_to_index.items()}
        # this is a sanity check after _remove_edges_not_in_nodes
        res._check_nodes_lineup_with_edges()
        return res


    def _featurize_nodes_to_dgl(
        self,
        res,
        X: pd.DataFrame,
        y: pd.DataFrame,
        use_scaler: str = None,
        feature_engine: FeatureEngine = "auto"
    ):
        logger.info("Running Node Featurization for DGL Graph")
        print(f'=*=*=Input shapes are data: {X.shape}, target: {y.shape}')

        X_enc, y_enc, res = res._featurize_or_get_nodes_dataframe_if_X_is_None(
            X=X, y=y, use_scaler=use_scaler, feature_engine=resolve_feature_engine(feature_engine)
        )

        print(f'=*=*=Encoded shapes are data: {X_enc.shape}, target: {y_enc.shape}')

        ndata = convert_to_torch(X_enc, y_enc)
        # add ndata to the graph
        res.DGL_graph.ndata.update(ndata)
        res._mask_nodes()
        return res

    def _featurize_edges_to_dgl(
        self,
        res,
        X: pd.DataFrame,
        y: pd.DataFrame,
        use_scaler: str = None,
        feature_engine: FeatureEngine = "auto"
    ):
        logger.info("Running Edge Featurization for DGL Graph")

        X_enc, y_enc, res = res._featurize_or_get_edges_dataframe_if_X_is_None(
            X=X, y=y, use_scaler=use_scaler, feature_engine=resolve_feature_engine(feature_engine)
        )
        
        edata = convert_to_torch(X_enc, y_enc)
        # add edata to the graph
        res.DGL_graph.edata.update(edata)
        res._mask_edges()
        return res

    def build_gnn(
        self,
        weight_column: str = None,
        X_nodes: XSymbolic = None,
        X_edges: XSymbolic = None,
        y_nodes: YSymbolic = None,
        y_edges: YSymbolic = None,
        use_node_scaler: str = 'robust',
        use_edge_scaler: str = 'robust',
        inplace: bool = False,
    ):

        if inplace:
            res = self
        else:
            res = self.bind()

        res.dgl_lazy_init()

        m = res.materialize_nodes()
        X_nodes_resolved = resolve_X(m._nodes, X_nodes)
        y_nodes_resolved = resolve_y(m._nodes, y_nodes)
        
        # here we check if edges are from UMAP, at which point X_edges should be none:
        if list(res._edges.columns) == ['_src_implicit', '_dst_implicit', '_weight']:
            logger.info(f'>>>EDGES ARE FROM UMAP, discarding explicit mention of X_edges')
            X_edges = None
            
        X_edges_resolved = resolve_X(res._edges, X_edges)
        y_edges_resolved = resolve_y(res._edges, y_edges)
        
        logger.info(f' >>>>>>>>>>>>>>>  Nodes: X_nodes_resolved, y_nodes_resolved is empty? {X_nodes_resolved.empty}, {y_nodes_resolved.empty}')
        logger.info(f' >>>>>>>>>>>>>>>  Edges: X_edges_resolved, y_edges_resolved is empty? {X_edges_resolved.empty}, {y_edges_resolved.empty}')

        if hasattr(res, "_MASK"):
            if y_edges_resolved is not None:
                y_edges_resolved = y_edges_resolved[res._MASK]  # automatically prune target using mask
                # note, edf, ndf, should both have unique indices

        # here we make node and edge features and add them to the DGL graph instance
        res = res._convert_edge_dataframe_to_DGL(weight_column, inplace)
        res = res._featurize_nodes_to_dgl(
            res, X_nodes_resolved, y_nodes_resolved, use_node_scaler
        )
        res = res._featurize_edges_to_dgl(
            res, X_edges_resolved, y_edges_resolved, use_edge_scaler
        )
        if not inplace:
            return res

    def _mask_nodes(self):
        if config.FEATURE in self.DGL_graph.ndata:
            n = self.DGL_graph.ndata[config.FEATURE].shape[0]
            (
                self.DGL_graph.ndata[config.TRAIN_MASK],
                self.DGL_graph.ndata[config.TEST_MASK],
            ) = get_torch_train_test_mask(n, self.train_split)

    def _mask_edges(self):
        if config.FEATURE in self.DGL_graph.edata:
            n = self.DGL_graph.edata[config.FEATURE].shape[0]
            (
                self.DGL_graph.edata[config.TRAIN_MASK],
                self.DGL_graph.edata[config.TEST_MASK],
            ) = get_torch_train_test_mask(n, self.train_split)

    def __getitem__(self, idx):
        # get one example by index
        if self.DGL_graph is None:
            logger.warn("DGL graph is not built, run `g.dgl_graph(..)` first")
        return self.DGL_graph

    def __len__(self):
        # number of data examples
        return 1
